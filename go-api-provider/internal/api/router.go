package api

import (
	"github.com/gin-contrib/cors"
	"github.com/gin-gonic/gin"
	"time"
)

func SetupRouter(handler *HTTPHandler) *gin.Engine {

	router := gin.Default()

	router.Use(cors.New(cors.Config{

		AllowOrigins:     []string{"http://localhost:3000"},
		AllowMethods:     []string{"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"},
		AllowHeaders:     []string{"Origin", "Content-Type", "Accept", "Authorization"},
		ExposeHeaders:    []string{"Content-Length"},
		AllowCredentials: true,
		MaxAge:           12 * time.Hour,
	}))

	apiGroup := router.Group("/api/v1")
	{
		apiGroup.POST("/scrape", handler.HandleScrapeURL)
		apiGroup.POST("/search", handler.HandleSearch)
		apiGroup.POST("/index", handler.HandleIndexDirect)
	}

	router.GET("/health", func(c *gin.Context) { /* ... */ })

	return router
}
