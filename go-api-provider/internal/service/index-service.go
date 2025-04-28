package service

import (
	"context"
	"fmt"
	"github.com/google/uuid"
	// "io"
	"log"
	"mime/multipart"
	// "net/http"
	"strings"

	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client"
	fpb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/featurepb"
	spb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/scrapepb"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/database"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/models"
)

type IndexService struct {
	repo        database.MediaRepository
	scraper     *client.ScraperClient
	featureExtr *client.FeatureExtractorClient
}

func NewIndexService(repo database.MediaRepository, sc *client.ScraperClient, fe *client.FeatureExtractorClient) *IndexService {
	return &IndexService{
		repo:        repo,
		scraper:     sc,
		featureExtr: fe,
	}
}

func (s *IndexService) RequestScrape(ctx context.Context, req models.ScrapeRequest) (string, string, error) {
	log.Printf("IndexService: Received request to scrape URL: %s", req.URL)

	if req.DepthLimit <= 0 {
		req.DepthLimit = 2
	}
	if req.CrawlStrategy == "" {
		req.CrawlStrategy = "default"
	}

	res, err := s.scraper.StartScrape(
		ctx,
		req.URL,
		req.AllowedDomains,
		int32(req.DepthLimit),
		req.CrawlStrategy,
		req.UsePlaywright,
	)
	if err != nil {
		return "", "REJECTED", fmt.Errorf("failed to start scrape job: %w", err)
	}

	if res.Status == spb.Status_REJECTED {
		return res.JobId, "REJECTED", fmt.Errorf("scrape job rejected by scraper service: %s", res.Message)
	}

	return res.JobId, "ACCEPTED", nil
}

func (s *IndexService) IndexDirectMedia(ctx context.Context, fileHeader *multipart.FileHeader, pageURL *string) error {
	log.Printf("IndexService: Received request to index direct media: %s", fileHeader.Filename)

	contentType := fileHeader.Header.Get("Content-Type")
	mediaType, err := determineMediaType(contentType, fileHeader.Filename)
	if err != nil {
		return fmt.Errorf("cannot determine media type: %w", err)
	}

	mediaURL, err := s.uploadMediaAndGetURL(ctx, fileHeader)
	if err != nil {
		return fmt.Errorf("failed to handle media upload: %w", err)
	}

	var protoMediaType fpb.MediaType
	switch mediaType {
	case models.ImageType:
		protoMediaType = fpb.MediaType_IMAGE
	case models.AudioType:
		protoMediaType = fpb.MediaType_AUDIO
	default:
		return fmt.Errorf("internal error: unhandled media type: %s", mediaType)
	}

	dbURL := mediaURL
	if pageURL != nil && *pageURL != "" {
		dbURL = *pageURL
	}

	itemsToProcess := []*fpb.UrlItem{
		{
			MediaUrl: mediaURL,
			Type:     protoMediaType,
			PageUrl:  dbURL,
		},
	}

	feRes, err := s.featureExtr.ProcessUrls(ctx, itemsToProcess, false)
	if err != nil {

		return fmt.Errorf("feature extraction failed: %w", err)
	}

	if len(feRes.Results) != 1 {

		return fmt.Errorf("unexpected number of results from feature extractor: %d", len(feRes.Results))
	}
	result := feRes.Results[0]

	if result.Status != fpb.Status_SUCCESS {

		return fmt.Errorf("feature extraction reported failure: Status=%s, Msg=%s", result.Status, result.ErrorMessage)
	}
	if len(result.FeatureVector) == 0 {

		return fmt.Errorf("feature extraction succeeded but returned empty vector")
	}

	vector, err := client.VectorFromBytes(result.FeatureVector)
	if err != nil {
		return fmt.Errorf("failed to deserialize feature vector: %w", err)
	}

	log.Printf("Saving extracted vector for URL: %s (Type: %s)", dbURL, mediaType)
	switch mediaType {
	case models.ImageType:
		err = s.repo.InsertImage(ctx, dbURL, vector)
	case models.AudioType:
		err = s.repo.InsertAudio(ctx, dbURL, vector)
	}
	if err != nil {

		return fmt.Errorf("failed to save vector to database: %w", err)
	}

	log.Printf("Successfully indexed direct media for URL: %s", dbURL)
	return nil
}

func (s *IndexService) uploadMediaAndGetURL(ctx context.Context, fileHeader *multipart.FileHeader) (string, error) {

	file, err := fileHeader.Open()
	if err != nil {
		return "", fmt.Errorf("failed to open uploaded file: %w", err)
	}
	defer file.Close()

	log.Printf("[Placeholder] Uploaded %s to temporary storage.", fileHeader.Filename)

	return fmt.Sprintf("http://temp-storage.example.com/%s/%s", uuid.NewString(), fileHeader.Filename), nil 

}

func determineMediaType(contentType, filename string) (models.MediaType, error) {

	if strings.HasPrefix(contentType, "image/") {
		return models.ImageType, nil
	}
	if strings.HasPrefix(contentType, "audio/") {
		return models.AudioType, nil
	}

	lowerFilename := strings.ToLower(filename)
	for _, ext := range []string{".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".tiff"} {
		if strings.HasSuffix(lowerFilename, ext) {
			return models.ImageType, nil
		}
	}
	for _, ext := range []string{".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"} {
		if strings.HasSuffix(lowerFilename, ext) {
			return models.AudioType, nil
		}
	}

	return "", fmt.Errorf("could not determine media type from Content-Type '%s' or filename '%s'", contentType, filename)
}
