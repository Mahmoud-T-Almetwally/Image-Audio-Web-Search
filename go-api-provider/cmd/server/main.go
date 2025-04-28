// cmd/server/main.go
package main

import (
	"context"
	"log"
	"net"      // For gRPC listener
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"
    "fmt"     // For formatting listener address

	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/api"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client"
	ipb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/indexingpb" // Import indexing proto
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/config"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/database"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/service"

	"google.golang.org/grpc"
)

func main() {
	// 1. Load Config (ensure GRPC_SERVER_PORT is loaded)
	cfg, err := config.LoadConfig(".") 
	if err != nil { log.Fatalf("Failed to load configuration: %v", err) }

	// 2. Init DB (no changes needed)
	db, err := database.ConnectDB(&cfg); if err != nil { /*...*/ }
    sqlDB, _ := db.DB(); defer sqlDB.Close() // Setup pool, defer close

	// 3. Init gRPC Clients (no changes needed)
	featureClient, err := client.NewFeatureExtractorClient(cfg.FeatureExtractorAddr); if err != nil { /*...*/ }; defer featureClient.Close()
	scraperClient, err := client.NewScraperClient(cfg.ScraperAddr); if err != nil { /*...*/ }; defer scraperClient.Close()

	// 4. Init Repository (no changes needed)
	mediaRepo := database.NewPostgresRepository(db)

	// 5. Init Services (no changes needed)
	indexService := service.NewIndexService(mediaRepo, scraperClient, featureClient, &cfg)
	searchService := service.NewSearchService(mediaRepo, featureClient, &cfg) 

	// 6. Init HTTP Handler (no changes needed)
	httpHandler := api.NewHTTPHandler(indexService, searchService, &cfg)

	// 7. Setup HTTP Router (no changes needed)
	httpRouter := api.SetupRouter(httpHandler)

	// 8. Start HTTP Server in Goroutine (no changes needed)
	httpServerAddr := ":" + cfg.HTTPServerPort
	httpSrv := &http.Server{ Addr: httpServerAddr, Handler: httpRouter }
	go func() {
		log.Printf("Starting HTTP server on %s", httpServerAddr)
		if err := httpSrv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("HTTP listen error: %s\n", err)
		}
	}()

    // === 9. Setup and Start gRPC Server ===
    grpcServerAddr := fmt.Sprintf(":%s", cfg.GRPCServerPort)
    lis, err := net.Listen("tcp", grpcServerAddr)
    if err != nil {
        log.Fatalf("Failed to listen for gRPC: %v", err)
    }

    // Create gRPC server instance
    grpcServer := grpc.NewServer() 
    
    // Create gRPC handler instance
    grpcHandler := api.NewGRPCHandler(indexService) 

    // Register gRPC services
    ipb.RegisterIndexingServiceServer(grpcServer, grpcHandler)
    // Register other gRPC services here if you add more later

    // Start gRPC server in a goroutine
    go func() {
        log.Printf("Starting gRPC server on %s", grpcServerAddr)
        if err := grpcServer.Serve(lis); err != nil {
            log.Fatalf("Failed to serve gRPC: %v", err)
        }
    }()
    // =====================================


	// 10. Wait for shutdown signal
	quit := make(chan os.Signal, 1)
	signal.Notify(quit, syscall.SIGINT, syscall.SIGTERM)
	<-quit 
	log.Println("Shutting down servers...")

	// --- Graceful Shutdown ---
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second) // Increased timeout slightly
	defer cancel()

	// Shutdown HTTP server
	log.Println("Shutting down HTTP server...")
	if err := httpSrv.Shutdown(ctx); err != nil {
		log.Printf("HTTP Server forced to shutdown: %v", err)
	}

    // Shutdown gRPC server
    log.Println("Shutting down gRPC server...")
    grpcServer.GracefulStop() // Preferred way to stop gRPC server

	log.Println("Servers exiting")
}