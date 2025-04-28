package client

import (
	"context"
	"fmt"
	"log"
	"unsafe"

	pb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/featurepb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
)

type FeatureExtractorClient struct {
	conn *grpc.ClientConn
	c    pb.FeatureServiceClient
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
		return nil, fmt.Errorf("invalid byte slice length: must be multiple of 4 for float32")
	}
	if len(data) == 0 {
		return []float32{}, nil
	}

	count := len(data) / 4

	bytePtr := unsafe.Pointer(&data[0])

	float32Slice := (*[1 << 30]float32)(bytePtr)[:count:count]

	result := make([]float32, count)
	copy(result, float32Slice)

	return result, nil
}
