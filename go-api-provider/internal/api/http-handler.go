package api

import (
	"log"
	"net/http"
	"strconv"

	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/models"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/service"
	"github.com/gin-gonic/gin"
)

type HTTPHandler struct {
	indexSvc  *service.IndexService
	searchSvc *service.SearchService
}

func NewHTTPHandler(indexSvc *service.IndexService, searchSvc *service.SearchService) *HTTPHandler {
	return &HTTPHandler{
		indexSvc:  indexSvc,
		searchSvc: searchSvc,
	}
}

func (h *HTTPHandler) HandleScrapeURL(c *gin.Context) {
	var req models.ScrapeRequest
	if err := c.ShouldBindJSON(&req); err != nil {
		log.Printf("Error binding scrape request: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request body: " + err.Error()})
		return
	}

	jobID, status, err := h.indexSvc.RequestScrape(c.Request.Context(), req)
	if err != nil {
		log.Printf("Error requesting scrape for URL %s: %v", req.URL, err)
		c.JSON(http.StatusInternalServerError, gin.H{
			"job_id":  jobID,
			"status":  status,
			"message": "Failed to initiate scrape job: " + err.Error(),
			"error":   err.Error(),
		})
		return
	}

	c.JSON(http.StatusAccepted, models.ScrapeResponse{
		JobID:   jobID,
		Status:  status,
		Message: "Scrape job accepted.",
	})
}

func (h *HTTPHandler) HandleSearch(c *gin.Context) {

	fileHeader, err := c.FormFile("media_file")
	if err != nil {
		log.Printf("Error getting file from form: %v", err)
		c.JSON(http.StatusBadRequest, gin.H{"error": "Missing or invalid 'media_file' field: " + err.Error()})
		return
	}

	limitStr := c.DefaultQuery("limit", "10")
	limit, err := strconv.Atoi(limitStr)
	if err != nil || limit <= 0 {
		limit = 10
	}

	log.Printf("Received search request with file: %s, limit: %d", fileHeader.Filename, limit)

	results, err := h.searchSvc.SearchByMedia(c.Request.Context(), fileHeader, limit)
	if err != nil {
		log.Printf("Error performing search for file %s: %v", fileHeader.Filename, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Search failed: " + err.Error()})
		return
	}

	c.JSON(http.StatusOK, models.SearchResponse{
		Results: results,
		Count:   len(results),
	})
}

func (h *HTTPHandler) HandleIndexDirect(c *gin.Context) {
	fileHeader, err := c.FormFile("media_file")
	if err != nil {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Missing 'media_file' field: " + err.Error()})
		return
	}

	pageURL := c.PostForm("page_url")
	var pageURLPtr *string
	if pageURL != "" {
		pageURLPtr = &pageURL
	}

	log.Printf("Received direct index request with file: %s, page_url: %v", fileHeader.Filename, pageURLPtr)

	err = h.indexSvc.IndexDirectMedia(c.Request.Context(), fileHeader, pageURLPtr)
	if err != nil {
		log.Printf("Error indexing direct media file %s: %v", fileHeader.Filename, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Direct indexing failed: " + err.Error()})
		return
	}

	c.JSON(http.StatusOK, gin.H{"message": "Media accepted for indexing."})
}
