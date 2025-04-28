package client

import (
	"context"
	"fmt"
	"log"

	pb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/scrapepb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type ScraperClient struct {
	conn *grpc.ClientConn
	c    pb.ScraperServiceClient
}

func NewScraperClient(address string) (*ScraperClient, error) {
	conn, err := grpc.NewClient(address, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, fmt.Errorf("did not connect to scraper service: %w", err)
	}
	log.Printf("Connected to Scraper gRPC service at %s", address)

	c := pb.NewScraperServiceClient(conn)
	return &ScraperClient{conn: conn, c: c}, nil
}

func (sc *ScraperClient) Close() error {
	log.Println("Closing connection to Scraper service...")
	if sc.conn != nil {
		return sc.conn.Close()
	}
	return nil
}

func (sc *ScraperClient) StartScrape(ctx context.Context, startURL string, allowedDomains string, depth int32, strategy string, usePlaywright bool) (*pb.StartScrapeResponse, error) {
	req := &pb.StartScrapeRequest{
		StartUrl:       startURL,
		AllowedDomains: allowedDomains,
		DepthLimit:     depth,
		CrawlStrategy:  strategy,
		UsePlaywright:  usePlaywright,
	}
	log.Printf("Sending StartScrape request for URL: %s", startURL)

	res, err := sc.c.StartScrape(ctx, req)
	if err != nil {
		log.Printf("Error calling StartScrape: %v", err)
		return nil, fmt.Errorf("gRPC call to StartScrape failed: %w", err)
	}
	log.Printf("Received StartScrape response: JobID=%s, Status=%s", res.JobId, res.Status)
	return res, nil
}
