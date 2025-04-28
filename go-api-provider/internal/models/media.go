package models

import (
	"github.com/pgvector/pgvector-go"
	"time"
)

type MediaType string

const (
	ImageType MediaType = "image"
	AudioType MediaType = "audio"
)

type Image struct {
	ID            uint            `gorm:"primaryKey"`
	PageURL       string          `gorm:"uniqueIndex;not null"`
	FeatureVector pgvector.Vector `gorm:"type:vector(1568);not null"`
	CreatedAt     time.Time
}

type Audio struct {
	ID            uint            `gorm:"primaryKey"`
	PageURL       string          `gorm:"uniqueIndex;not null"`
	FeatureVector pgvector.Vector `gorm:"type:vector(768);not null"`
	CreatedAt     time.Time
}

type ScrapeRequest struct {
	URL            string `json:"url" binding:"required,url"`
	AllowedDomains string `json:"allowed_domains,omitempty"`
	DepthLimit     int    `json:"depth_limit,omitempty"`
	CrawlStrategy  string `json:"crawl_strategy,omitempty"`
	UsePlaywright  bool   `json:"use_playwright"`
}

type ScrapeResponse struct {
	JobID   string `json:"job_id"`
	Status  string `json:"status"`
	Message string `json:"message"`
}

type SearchResult struct {
	PageURL    string    `json:"page_url"`
	Similarity float64   `json:"similarity"`
	MediaType  MediaType `json:"media_type"`
}

type SearchResponse struct {
	Results []SearchResult `json:"results"`
	Count   int            `json:"count"`
}

type MediaInfo struct {
	PageURL   string
	MediaType MediaType
	Vector    []float32
}
