package client

import (
	"bytes"
	"context"
	"encoding/binary"
	"fmt"
	"log"
	"math"

	pb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/featurepb"
	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/keepalive"
	"time"
)

var kacp = keepalive.ClientParameters{
	Time:                10 * time.Second,
	Timeout:             time.Second,
	PermitWithoutStream: true,
}

type FeatureExtractorClient struct {
	conn         *grpc.ClientConn
	urlService   pb.FeatureUrlServiceClient
	bytesService pb.FeatureBytesServiceClient
}

func NewFeatureExtractorClient(address string) (*FeatureExtractorClient, error) {

	opts := []grpc.DialOption{
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithKeepaliveParams(kacp),

		grpc.WithDefaultCallOptions(
			grpc.MaxCallRecvMsgSize(50*1024*1024),
			grpc.MaxCallSendMsgSize(50*1024*1024),
		),
	}

	conn, err := grpc.NewClient(address, opts...)
	if err != nil {
		return nil, fmt.Errorf("did not connect to feature extractor service at %s: %w", address, err)
	}
	log.Printf("Connected to Feature Extractor gRPC service at %s", address)

	urlClient := pb.NewFeatureUrlServiceClient(conn)
	bytesClient := pb.NewFeatureBytesServiceClient(conn)

	return &FeatureExtractorClient{
		conn:         conn,
		urlService:   urlClient,
		bytesService: bytesClient,
	}, nil
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

	res, err := fc.urlService.ProcessUrls(ctx, req)
	if err != nil {
		log.Printf("Error calling ProcessUrls: %v", err)
		return nil, fmt.Errorf("gRPC call to ProcessUrls failed: %w", err)
	}
	log.Printf("Received ProcessUrls response with %d results", len(res.Results))
	return res, nil
}

func (fc *FeatureExtractorClient) ProcessBytes(ctx context.Context, items []*pb.MediaItemBytes, applyDenoising bool) (*pb.ProcessBytesResponse, error) {
	req := &pb.ProcessBytesRequest{
		Items:          items,
		ApplyDenoising: applyDenoising,
	}
	log.Printf("Sending ProcessBytes request with %d items to Feature Extractor", len(items))

	res, err := fc.bytesService.ProcessBytes(ctx, req)
	if err != nil {
		log.Printf("Error calling ProcessBytes: %v", err)
		return nil, fmt.Errorf("gRPC call to ProcessBytes failed: %w", err)
	}
	log.Printf("Received ProcessBytes response with %d results", len(res.Results))
	return res, nil
}

func VectorFromBytes(data []byte) ([]float32, error) {
	if len(data)%4 != 0 {
		return nil, fmt.Errorf("invalid byte slice length (%d): must be multiple of 4 for float32", len(data))
	}
	if len(data) == 0 {
		return []float32{}, nil
	}
	count := len(data) / 4
	result := make([]float32, count)
	byteReader := bytes.NewReader(data)
	err := binary.Read(byteReader, binary.LittleEndian, &result)
	if err != nil {
		return nil, fmt.Errorf("failed to read bytes into float32 slice: %w", err)
	}
	if byteReader.Len() != 0 {
		return nil, fmt.Errorf("byte reader has %d remaining bytes after reading floats", byteReader.Len())
	}
	for i, v := range result {
		if math.IsNaN(float64(v)) || math.IsInf(float64(v), 0) {
			return nil, fmt.Errorf("deserialized vector contains NaN or Inf at index %d", i)
		}
	}
	return result, nil
}
