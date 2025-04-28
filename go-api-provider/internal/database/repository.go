package database

import (
	"context"
	"fmt"
	"log"

	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/models"
	"github.com/pgvector/pgvector-go"
	"gorm.io/gorm"
	"gorm.io/gorm/clause"
)

type MediaRepository interface {
	InsertImage(ctx context.Context, pageURL string, vector []float32) error
	InsertAudio(ctx context.Context, pageURL string, vector []float32) error
	FindSimilarImages(ctx context.Context, queryVector []float32, limit int) ([]models.SearchResult, error)
	FindSimilarAudio(ctx context.Context, queryVector []float32, limit int) ([]models.SearchResult, error)

	CheckPageURLExists(ctx context.Context, pageURL string, mediaType models.MediaType) (bool, error)
}

type postgresRepository struct {
	db *gorm.DB
}

func NewPostgresRepository(db *gorm.DB) MediaRepository {
	return &postgresRepository{db: db}
}

func (r *postgresRepository) InsertImage(ctx context.Context, pageURL string, vector []float32) error {
	img := models.Image{
		PageURL:       pageURL,
		FeatureVector: pgvector.NewVector(vector),
	}

	result := r.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "page_url"}},
		DoNothing: true,
	}).Create(&img)

	if result.Error != nil {
		return fmt.Errorf("failed to insert image (page_url: %s): %w", pageURL, result.Error)
	}
	if result.RowsAffected == 0 {
		log.Printf("Image with page_url %s already exists, insertion skipped.", pageURL)
	} else {
		log.Printf("Inserted image for page_url %s.", pageURL)
	}
	return nil
}

func (r *postgresRepository) InsertAudio(ctx context.Context, pageURL string, vector []float32) error {
	aud := models.Audio{
		PageURL:       pageURL,
		FeatureVector: pgvector.NewVector(vector),
	}
	result := r.db.WithContext(ctx).Clauses(clause.OnConflict{
		Columns:   []clause.Column{{Name: "page_url"}},
		DoNothing: true,
	}).Create(&aud)

	if result.Error != nil {
		return fmt.Errorf("failed to insert audio (page_url: %s): %w", pageURL, result.Error)
	}
	if result.RowsAffected == 0 {
		log.Printf("Audio with page_url %s already exists, insertion skipped.", pageURL)
	} else {
		log.Printf("Inserted audio for page_url %s.", pageURL)
	}
	return nil
}

func (r *postgresRepository) FindSimilarImages(ctx context.Context, queryVector []float32, limit int) ([]models.SearchResult, error) {
	var results []models.SearchResult
	queryPgVec := pgvector.NewVector(queryVector)

	err := r.db.WithContext(ctx).
		Table("images").
		Select("page_url, 1 - (feature_vector <=> ?) AS similarity", queryPgVec).
		Order("similarity DESC").
		Limit(limit).
		Find(&results).Error

	if err != nil {
		return nil, fmt.Errorf("failed to find similar images: %w", err)
	}

	for i := range results {
		results[i].MediaType = models.ImageType
	}
	return results, nil
}

func (r *postgresRepository) FindSimilarAudio(ctx context.Context, queryVector []float32, limit int) ([]models.SearchResult, error) {
	var results []models.SearchResult
	queryPgVec := pgvector.NewVector(queryVector)

	err := r.db.WithContext(ctx).
		Table("audio").
		Select("page_url, 1 - (feature_vector <=> ?) AS similarity", queryPgVec).
		Order("similarity DESC").
		Limit(limit).
		Find(&results).Error

	if err != nil {
		return nil, fmt.Errorf("failed to find similar audio: %w", err)
	}

	for i := range results {
		results[i].MediaType = models.AudioType
	}
	return results, nil
}

func (r *postgresRepository) CheckPageURLExists(ctx context.Context, pageURL string, mediaType models.MediaType) (bool, error) {
	var count int64
	var err error
	tableName := ""

	switch mediaType {
	case models.ImageType:
		tableName = "images"
	case models.AudioType:
		tableName = "audio"
	default:
		return false, fmt.Errorf("unsupported media type: %s", mediaType)
	}

	err = r.db.WithContext(ctx).Table(tableName).Where("page_url = ?", pageURL).Count(&count).Error
	if err != nil {
		return false, fmt.Errorf("failed to check existence for page_url %s in %s: %w", pageURL, tableName, err)
	}

	return count > 0, nil
}
