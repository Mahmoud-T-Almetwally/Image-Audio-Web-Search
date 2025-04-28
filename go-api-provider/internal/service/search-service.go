package service

import (
	"context"
	"fmt"
	"github.com/google/uuid"
	"log"
	"mime/multipart"
	"os"

	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client"
	fpb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/featurepb"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/config"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/database"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/models"
)

type SearchService struct {
	repo        database.MediaRepository
	featureExtr *client.FeatureExtractorClient
	cfg         *config.Config
}

func NewSearchService(repo database.MediaRepository, fe *client.FeatureExtractorClient, cfg *config.Config) *SearchService {
	return &SearchService{
		repo:        repo,
		featureExtr: fe,
		cfg:         cfg,
	}
}

func (s *SearchService) SearchByMedia(ctx context.Context, fileHeader *multipart.FileHeader, limit int) ([]models.SearchResult, error) {
	log.Printf("SearchService: Received search request with media: %s", fileHeader.Filename)

	contentType := fileHeader.Header.Get("Content-Type")
	mediaType, err := determineMediaType(contentType, fileHeader.Filename)
	if err != nil {
		return nil, fmt.Errorf("cannot determine media type for search: %w", err)
	}

	// mediaURL, err := s.uploadMediaAndGetURL(ctx, fileHeader)
	// if err != nil {
	// 	return nil, fmt.Errorf("failed to handle media upload for search: %w", err)
	// }

	localFilePath, mediaURL, err := saveTempMediaAndGetURL(fileHeader, s.cfg.TempMediaDir, s.cfg.APIBaseURL)
	if err != nil {
		return nil, fmt.Errorf("failed to save temporary media for search: %w", err)
	}
    // ** Schedule cleanup **
	defer func() {
		log.Printf("Attempting cleanup of temporary search file: %s", localFilePath)
		err := os.Remove(localFilePath)
		if err != nil && !os.IsNotExist(err) {
			log.Printf("Error deleting temporary search file %s: %v", localFilePath, err)
		} else if err == nil {
			log.Printf("Successfully deleted temporary search file: %s", localFilePath)
		}
	}()

	var protoMediaType fpb.MediaType
	switch mediaType {
	case models.ImageType:
		protoMediaType = fpb.MediaType_IMAGE
	case models.AudioType:
		protoMediaType = fpb.MediaType_AUDIO
	default:
		return nil, fmt.Errorf("internal error: unhandled media type: %s", mediaType)
	}

	itemsToProcess := []*fpb.UrlItem{
		{MediaUrl: mediaURL, Type: protoMediaType, PageUrl: mediaURL},
	}

	feRes, err := s.featureExtr.ProcessUrls(ctx, itemsToProcess, false)
	if err != nil {
		return nil, fmt.Errorf("query feature extraction failed: %w", err)
	}

	if len(feRes.Results) != 1 {
		return nil, fmt.Errorf("unexpected results from feature extractor: %d", len(feRes.Results))
	}
	result := feRes.Results[0]
	if result.Status != fpb.Status_SUCCESS {
		return nil, fmt.Errorf("query feature extraction failed: Status=%s, Msg=%s", result.Status, result.ErrorMessage)
	}
	if len(result.FeatureVector) == 0 {
		return nil, fmt.Errorf("query feature extraction returned empty vector")
	}

	queryVector, err := client.VectorFromBytes(result.FeatureVector)
	if err != nil {
		return nil, fmt.Errorf("failed to deserialize query vector: %w", err)
	}

	limitToUse := s.cfg.DefaultSearchLimit // Use config default (e.g., 10)
	if limitToUse <= 0 {
		limitToUse = 10 // Fallback if config is zero
	}

	var searchResults []models.SearchResult
	log.Printf("Performing similarity search (Type: %s, Limit: %d)", mediaType, limitToUse) // Log the actual limit used
	switch mediaType {
	case models.ImageType:
		searchResults, err = s.repo.FindSimilarImages(ctx, queryVector, limitToUse) // Pass hardcoded/config limit
	case models.AudioType:
		searchResults, err = s.repo.FindSimilarAudio(ctx, queryVector, limitToUse) // Pass hardcoded/config limit
	}


	if err != nil {
		return nil, fmt.Errorf("database similarity search failed: %w", err)
	}

	log.Printf("Found %d similar results.", len(searchResults))

	return searchResults, nil
}

func (s *SearchService) uploadMediaAndGetURL(ctx context.Context, fileHeader *multipart.FileHeader) (string, error) {

	file, err := fileHeader.Open()
	if err != nil {
		return "", fmt.Errorf("failed to open uploaded file: %w", err)
	}
	defer file.Close()
	log.Printf("[Placeholder] Uploaded %s to temporary storage for search.", fileHeader.Filename)
	return fmt.Sprintf("http://temp-storage.example.com/search/%s/%s", uuid.NewString(), fileHeader.Filename), nil 

}
