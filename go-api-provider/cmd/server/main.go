package main

import (
	"context"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/api"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/config"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/database"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/service"
)

func main() {

	cfg, err := config.LoadConfig(".")
	if err != nil {
		log.Fatalf("Failed to load configuration: %v", err)
	}

	db, err := database.ConnectDB(&cfg)
	if err != nil {
		log.Fatalf("Failed to connect to database: %v", err)
	}

	sqlDB, err := db.DB()
	if err != nil {
		log.Fatalf("Failed to get underlying sql.DB: %v", err)
	}
	defer func() {
		log.Println("Closing database connection...")
		if err := sqlDB.Close(); err != nil {
			log.Printf("Error closing database: %v", err)
		}
	}()

	sqlDB.SetMaxIdleConns(10)
	sqlDB.SetMaxOpenConns(100)
	sqlDB.SetConnMaxLifetime(time.Hour)

	featureClient, err := client.NewFeatureExtractorClient(cfg.FeatureExtractorAddr)
	if err != nil {
		log.Fatalf("Failed to create feature extractor client: %v", err)
	}
	defer featureClient.Close()

	scraperClient, err := client.NewScraperClient(cfg.ScraperAddr)
	if err != nil {
		log.Fatalf("Failed to create scraper client: %v", err)
	}
	defer scraperClient.Close()

	mediaRepo := database.NewPostgresRepository(db)

	indexService := service.NewIndexService(mediaRepo, scraperClient, featureClient)
	searchService := service.NewSearchService(mediaRepo, featureClient, &cfg)

	httpHandler := api.NewHTTPHandler(indexService, searchService)

	router := api.SetupRouter(httpHandler)

	serverAddr := ":" + cfg.HTTPServerPort
	log.Printf("Starting HTTP server on %s", serverAddr)

	srv := &http.Server{
		Addr:    serverAddr,
		Handler: router,
	}

	go func() {
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("listen: %s\n", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down server...")

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	if err := srv.Shutdown(ctx); err != nil {
		log.Fatal("Server forced to shutdown:", err)
	}

	log.Println("Server exiting")
}
