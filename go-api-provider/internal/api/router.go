package api

import (
	"github.com/gin-gonic/gin"
)

func SetupRouter(handler *HTTPHandler) *gin.Engine {

	router := gin.Default()

	apiGroup := router.Group("/api/v1") 
	{
		apiGroup.POST("/scrape", handler.HandleScrapeURL)
		apiGroup.POST("/search", handler.HandleSearch)
		apiGroup.POST("/index", handler.HandleIndexDirect) 
	}

	router.GET("/temp_media/:filename", handler.HandleServeTempMedia) 

	router.GET("/health", func(c *gin.Context) { /* ... */ })

	return router
}
