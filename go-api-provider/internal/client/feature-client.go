package client

import (
	"bytes"
	"encoding/binary"
	"math"
	"context"
	"fmt"
	"log"

	pb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/featurepb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type FeatureExtractorClient struct {
	conn *grpc.ClientConn
	c    pb.FeatureBytesServiceClient
}

func NewFeatureExtractorClient(address string) (*FeatureExtractorClient, error) {

	conn, err := grpc.Dial(address, grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		return nil, fmt.Errorf("did not connect to feature extractor service: %w", err)
	}
	log.Printf("Connected to Feature Extractor gRPC service at %s", address)

	c := pb.NewFeatureServiceClient(conn)
	return &FeatureExtractorClient{conn: conn, c: c}, nil
}

func (fc *FeatureExtractorClient) Close() error {
	log.Println("Closing connection to Feature Extractor service...")
	if fc.conn != nil {
		return fc.conn.Close()
	}
	return nil
}

func (fc *FeatureExtractorClient) ProcessUrls(ctx context.Context, items []*pb.UrlItem, applyDenoising bool) (*pb.ProcessUrlsResponse, error) {
	req := &pb.ProcessUrlsRequest{
		Items:          items,
		ApplyDenoising: applyDenoising,
	}
	log.Printf("Sending ProcessUrls request with %d items to Feature Extractor", len(items))

	res, err := fc.c.ProcessUrls(ctx, req)
	if err != nil {
		log.Printf("Error calling ProcessUrls: %v", err)
		return nil, fmt.Errorf("gRPC call to ProcessUrls failed: %w", err)
	}
	log.Printf("Received ProcessUrls response with %d results", len(res.Results))
	return res, nil
}

func VectorFromBytes(data []byte) ([]float32, error) {
	if len(data)%4 != 0 {
		return nil, fmt.Errorf("invalid byte slice length (%d): must be multiple of 4 for float32", len(data))
	}
	if len(data) == 0 {
		return []float32{}, nil // Handle empty case explicitly
	}

	count := len(data) / 4
	result := make([]float32, count)
	byteReader := bytes.NewReader(data) // Create a reader for the byte slice

	// Use binary.Read to read into the float32 slice
	// Specify LittleEndian byte order (adjust if Python side uses different order)
	err := binary.Read(byteReader, binary.LittleEndian, &result)
	if err != nil {
		return nil, fmt.Errorf("failed to read bytes into float32 slice: %w", err)
	}
    
    // The binary.Read should have consumed all bytes if lengths match
    if byteReader.Len() != 0 {
        return nil, fmt.Errorf("byte reader has %d remaining bytes after reading floats", byteReader.Len())
    }

	// Optional: Check for NaN/Inf (safer here as values are properly converted)
	for i, v := range result {
		if math.IsNaN(float64(v)) || math.IsInf(float64(v), 0) {
			// Provide more context in error if needed
			return nil, fmt.Errorf("deserialized vector contains NaN or Inf at index %d", i)
		}
	}

	return result, nil
}
