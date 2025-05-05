package main

import (
	"context"
	"fmt"
	"log"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/api"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client"
	ipb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/indexingpb"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/config"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/database"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/service"
	"google.golang.org/grpc"
)

func main() {

	configPath := "../../config.env"

	cfg, err := config.LoadConfig(configPath)
	if err != nil {
		log.Printf("error occured while loading to load configuration: %v", err)
	}

	db, err := database.ConnectDB(&cfg)
	if err != nil { /*...*/
	}
	sqlDB, _ := db.DB()
	defer sqlDB.Close()

	featureClient, err := client.NewFeatureExtractorClient(cfg.FeatureExtractorAddr)
	if err != nil { 
		log.Printf("Failed to connect to feature extraction service: %v", err)
	}
	defer featureClient.Close()
	scraperClient, err := client.NewScraperClient(cfg.ScraperAddr)
	if err != nil { 
		log.Printf("Failed to connect to web scrape service: %v", err)
	}
	defer scraperClient.Close()

	mediaRepo := database.NewPostgresRepository(db)

	indexService := service.NewIndexService(mediaRepo, scraperClient, featureClient, &cfg)
	searchService := service.NewSearchService(mediaRepo, featureClient, &cfg)

	httpHandler := api.NewHTTPHandler(indexService, searchService)

	httpRouter := api.SetupRouter(httpHandler)

	httpServerAddr := ":" + cfg.HTTPServerPort
	httpSrv := &http.Server{Addr: httpServerAddr, Handler: httpRouter}
	go func() {
		log.Printf("Starting HTTP server on %s", httpServerAddr)
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("HTTP listen error: %s\n", err)
		}
	}()

	grpcServerAddr := fmt.Sprintf(":%s", cfg.GRPCServerPort)
	lis, err := net.Listen("tcp", grpcServerAddr)
	if err != nil {
		log.Fatalf("Failed to listen for gRPC: %v", err)
	}

	grpcServer := grpc.NewServer()

	grpcHandler := api.NewGRPCHandler(indexService)

	ipb.RegisterIndexingServiceServer(grpcServer, grpcHandler)

	go func() {
		log.Printf("Starting gRPC server on %s", grpcServerAddr)
		if err := grpcServer.Serve(lis); err != nil {
			log.Fatalf("Failed to serve gRPC: %v", err)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit
	log.Println("Shutting down servers...")

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	log.Println("Shutting down HTTP server...")
	if err := httpSrv.Shutdown(ctx); err != nil {
		log.Printf("HTTP Server forced to shutdown: %v", err)
	}

	log.Println("Shutting down gRPC server...")
	grpcServer.GracefulStop()

	log.Println("Servers exiting")
}
