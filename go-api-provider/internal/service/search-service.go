package service

import (
	"context"
	"fmt"
	"io"
	"log"
	"mime/multipart"

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

	file, err := fileHeader.Open()
	if err != nil {
		return nil, fmt.Errorf("failed to open uploaded search file: %w", err)
	}
	defer file.Close()

	fileBytes, err := io.ReadAll(file)
	if err != nil {
		return nil, fmt.Errorf("failed to read uploaded search file: %w", err)
	}
	if len(fileBytes) == 0 {
		return nil, fmt.Errorf("uploaded search file is empty")
	}

	var protoMediaType fpb.MediaType
	switch mediaType {
	case models.ImageType:
		protoMediaType = fpb.MediaType_IMAGE
	case models.AudioType:
		protoMediaType = fpb.MediaType_AUDIO
	default:
		return nil, fmt.Errorf("internal error: unhandled media type: %s", mediaType)
	}

	referenceID := fileHeader.Filename
	itemsToProcess := []*fpb.MediaItemBytes{
		{
			MediaContent: fileBytes,
			MediaType:    protoMediaType,
			ReferenceId:  referenceID,
		},
	}

	feRes, err := s.featureExtr.ProcessBytes(ctx, itemsToProcess, false)
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

	limitToUse := limit
	if limitToUse <= 0 {
		limitToUse = s.cfg.DefaultSearchLimit
	}

	var searchResults []models.SearchResult
	log.Printf("Performing similarity search (Type: %s, Limit: %d)", mediaType, limitToUse)
	switch mediaType {
	case models.ImageType:
		searchResults, err = s.repo.FindSimilarImages(ctx, queryVector, limitToUse)
	case models.AudioType:
		searchResults, err = s.repo.FindSimilarAudio(ctx, queryVector, limitToUse)
	}

	if err != nil {
		return nil, fmt.Errorf("database similarity search failed: %w", err)
	}

	log.Printf("Found %d similar results.", len(searchResults))

	return searchResults, nil
}
