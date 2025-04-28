package service

import (
	"context"
	"fmt"
	"io"
	"log"
	"mime/multipart"

	"runtime"
	"strings"

	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client"
	fpb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/featurepb"
	ipb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/indexingpb"
	spb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/scrapepb"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/config"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/database"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/models"

	"golang.org/x/sync/errgroup"
)

func (s *IndexService) HandleScrapedBatch(ctx context.Context, batchItems []*ipb.ScrapedItem, jobID string) (processedCount, failedCount int, err error) {
	itemCount := len(batchItems)
	log.Printf("[Job %s] IndexService: Handling batch of %d scraped items", jobID, itemCount)

	concurrencyLimit := runtime.GOMAXPROCS(0) * 2
	g, childCtx := errgroup.WithContext(ctx)
	g.SetLimit(concurrencyLimit)

	processedChan := make(chan bool, itemCount)
	failedChan := make(chan bool, itemCount)

	for _, item := range batchItems {

		currentItem := item

		g.Go(func() error {

			err := s.processSingleScrapedItem(childCtx, currentItem)
			if err != nil {
				log.Printf("[Job %s] Failed processing item (Page: %s, Media: %s): %v", jobID, currentItem.PageUrl, currentItem.MediaUrl, err)
				failedChan <- true

				return nil
			} else {
				processedChan <- true
			}
			return nil
		})
	}

	groupErr := g.Wait()

	close(processedChan)
	close(failedChan)
	for range processedChan {
		processedCount++
	}
	for range failedChan {
		failedCount++
	}

	log.Printf("[Job %s] Batch processing finished. Processed: %d, Failed: %d", jobID, processedCount, failedCount)

	if groupErr != nil {
		return processedCount, failedCount, fmt.Errorf("error during batch processing: %w", groupErr)
	}
	return processedCount, failedCount, nil
}

func (s *IndexService) processSingleScrapedItem(ctx context.Context, item *ipb.ScrapedItem) error {
	pageURL := item.PageUrl
	mediaURL := item.MediaUrl

	var modelMediaType models.MediaType
	var featureProtoMediaType fpb.MediaType
	switch item.MediaType {
	case ipb.MediaType_IMAGE:
		modelMediaType = models.ImageType
		featureProtoMediaType = fpb.MediaType_IMAGE
	case ipb.MediaType_AUDIO:
		modelMediaType = models.AudioType
		featureProtoMediaType = fpb.MediaType_AUDIO
	default:
		return fmt.Errorf("unsupported media type enum value: %v", item.MediaType)
	}

	exists, err := s.repo.CheckPageURLExists(ctx, pageURL, modelMediaType)
	if err != nil {

		return fmt.Errorf("database check failed for page %s: %w", pageURL, err)
	}
	if exists {
		log.Printf("Skipping already indexed page URL: %s (Type: %s)", pageURL, modelMediaType)
		return nil
	}

	feItems := []*fpb.UrlItem{
		{
			MediaUrl: mediaURL,
			Type:     featureProtoMediaType,
			PageUrl:  pageURL,
		},
	}

	feRes, err := s.featureExtr.ProcessUrls(ctx, feItems, false)
	if err != nil {
		return fmt.Errorf("feature extraction gRPC call failed for media %s: %w", mediaURL, err)
	}

	if len(feRes.Results) != 1 {
		return fmt.Errorf("unexpected FE result count (%d) for media %s", len(feRes.Results), mediaURL)
	}
	result := feRes.Results[0]

	if result.Status != fpb.Status_SUCCESS {
		return fmt.Errorf("feature extraction failed for media %s: Status=%s, Msg=%s", mediaURL, result.Status, result.ErrorMessage)
	}
	if len(result.FeatureVector) == 0 {
		return fmt.Errorf("feature extraction succeeded but returned empty vector for media %s", mediaURL)
	}

	vector, err := client.VectorFromBytes(result.FeatureVector)
	if err != nil {
		return fmt.Errorf("failed to deserialize feature vector for media %s: %w", mediaURL, err)
	}

	log.Printf("Saving vector for page URL: %s (Type: %s)", pageURL, modelMediaType)
	switch modelMediaType {
	case models.ImageType:
		err = s.repo.InsertImage(ctx, pageURL, vector)
	case models.AudioType:
		err = s.repo.InsertAudio(ctx, pageURL, vector)
	}
	if err != nil {
		return fmt.Errorf("database insert failed for page %s: %w", pageURL, err)
	}

	log.Printf("Successfully processed and saved item for page: %s", pageURL)
	return nil
}

type IndexService struct {
	repo        database.MediaRepository
	scraper     *client.ScraperClient
	featureExtr *client.FeatureExtractorClient
	cfg         *config.Config
}

func NewIndexService(repo database.MediaRepository, sc *client.ScraperClient, fe *client.FeatureExtractorClient, cfg *config.Config) *IndexService {
	return &IndexService{
		repo:        repo,
		scraper:     sc,
		featureExtr: fe,
		cfg:         cfg,
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

	file, err := fileHeader.Open()
	if err != nil {
		return fmt.Errorf("failed to open uploaded file for indexing: %w", err)
	}
	defer file.Close()

	fileBytes, err := io.ReadAll(file)
	if err != nil {
		return fmt.Errorf("failed to read uploaded file for indexing: %w", err)
	}
	if len(fileBytes) == 0 {
		return fmt.Errorf("uploaded file for indexing is empty")
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

	var dbURL string
	if pageURL != nil && *pageURL != "" {
		dbURL = *pageURL
	} else {

		return fmt.Errorf("page_url must be provided for direct indexing")
	}

	exists, err := s.repo.CheckPageURLExists(ctx, dbURL, mediaType)
	if err != nil {
		return fmt.Errorf("database check failed for page %s: %w", dbURL, err)
	}
	if exists {
		log.Printf("Skipping already indexed page URL via direct upload: %s (Type: %s)", dbURL, mediaType)
		return nil
	}

	itemsToProcess := []*fpb.MediaItemBytes{
		{
			MediaContent: fileBytes,
			MediaType:    protoMediaType,
			ReferenceId:  dbURL,
		},
	}

	feRes, err := s.featureExtr.ProcessBytes(ctx, itemsToProcess, false)
	if err != nil {
		return fmt.Errorf("feature extraction failed: %w", err)
	}

	if len(feRes.Results) != 1 {
		return fmt.Errorf("unexpected results from feature extractor: %d", len(feRes.Results))
	}
	result := feRes.Results[0]
	if result.Status != fpb.Status_SUCCESS {
		return fmt.Errorf("feature extraction reported failure: Status=%s, Msg=%s", result.Status, result.ErrorMessage)
	}
	if len(result.FeatureVector) == 0 {
		return fmt.Errorf("feature extraction succeeded but returned empty vector")
	}

	if result.Url != dbURL {
		log.Printf("Warning: Reference ID mismatch in FE response. Expected %s, got %s", dbURL, result.Url)

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
