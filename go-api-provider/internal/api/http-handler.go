package api

import (
	"log"
	"net/http"
	"strings"
	"path/filepath"
	"os"

	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/models"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/config"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/service"
	"github.com/gin-gonic/gin"
)

type HTTPHandler struct {
	indexSvc  *service.IndexService
	searchSvc *service.SearchService
	cfg *config.Config
}

func NewHTTPHandler(indexSvc *service.IndexService, searchSvc *service.SearchService, cfg *config.Config) *HTTPHandler {
	return &HTTPHandler{
		indexSvc:  indexSvc,
		searchSvc: searchSvc,
		cfg: cfg,
	}
}


func (h *HTTPHandler) HandleServeTempMedia(c *gin.Context) {
	filename := c.Param("filename") // Get filename from URL path

	// **Security:** Basic validation to prevent directory traversal.
	// Ensure filename doesn't contain path separators.
	if filename == "" || strings.Contains(filename, "/") || strings.Contains(filename, "\\") || strings.Contains(filename, "..") {
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid filename"})
		return
	}

	// Construct the full path safely
	filePath := filepath.Join(h.cfg.TempMediaDir, filename)

	// Check if file exists and is not a directory before serving
	fileInfo, err := os.Stat(filePath)
	if os.IsNotExist(err) {
		log.Printf("Attempt to serve non-existent temp file: %s", filePath)
		c.JSON(http.StatusNotFound, gin.H{"error": "File not found"})
		return
	}
	if err != nil {
		log.Printf("Error stating temp file %s: %v", filePath, err)
		c.JSON(http.StatusInternalServerError, gin.H{"error": "Internal server error"})
		return
	}
	if fileInfo.IsDir() {
		log.Printf("Attempt to serve directory as temp file: %s", filePath)
		c.JSON(http.StatusBadRequest, gin.H{"error": "Invalid request"})
		return
	}

	// Serve the file
	// Let Gin/http handle Content-Type detection based on extension
	log.Printf("Serving temp file: %s", filePath)
	c.File(filePath)
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
	if err != nil { /* ... error handling ... */ return }

	// --- Remove limit/offset parsing ---
	// limitStr := c.DefaultQuery("limit", "10") 
	// limit, err := strconv.Atoi(limitStr)
	// if err != nil || limit <= 0 {
	// 	limit = 10 
	// }
    // Hardcode limit (or get from config if preferred for default)
	const searchLimit = 10 

	log.Printf("Received search request with file: %s, limit: %d", fileHeader.Filename, searchLimit)

	// Call service with hardcoded limit
	results, err := h.searchSvc.SearchByMedia(c.Request.Context(), fileHeader, searchLimit) 
	if err != nil { /* ... error handling ... */ return }

	// Return results (max 10)
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
