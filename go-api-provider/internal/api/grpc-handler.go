
package api

import (
	"context"
	"log"
	"fmt"

	ipb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/indexingpb" 
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/service"
	"google.golang.org/grpc/codes" 
	"google.golang.org/grpc/status"
)


type GRPCHandler struct {
	ipb.UnimplementedIndexingServiceServer 
	indexSvc *service.IndexService
}


func NewGRPCHandler(indexSvc *service.IndexService) *GRPCHandler {
	return &GRPCHandler{indexSvc: indexSvc}
}


func (h *GRPCHandler) ProcessScrapedItems(ctx context.Context, req *ipb.ProcessScrapedItemsRequest) (*ipb.ProcessScrapedItemsResponse, error) {
	jobID := req.GetJobId() 
	items := req.GetItems()
	receivedCount := len(items)

	if receivedCount == 0 {
		log.Printf("[Job %s] Received empty batch in ProcessScrapedItems", jobID)
		return &ipb.ProcessScrapedItemsResponse{Message: "Received empty batch"}, nil
	}

	log.Printf("[Job %s] gRPC Handler received ProcessScrapedItems request with %d items.", jobID, receivedCount)

	processed, failed, err := h.indexSvc.HandleScrapedBatch(ctx, items, jobID)
	if err != nil {
		
		log.Printf("[Job %s] Error handling scraped batch: %v", jobID, err)
		
		
		return nil, status.Errorf(codes.Internal, "failed to process batch (job %s): %v", jobID, err)
	}

	resp := &ipb.ProcessScrapedItemsResponse{
		ItemsReceived: int32(receivedCount),
		ItemsProcessed: int32(processed),
		ItemsFailed:    int32(failed),
		Message:        fmt.Sprintf("Batch processed for job %s. Results - Processed: %d, Failed: %d", jobID, processed, failed),
	}
	log.Printf("[Job %s] Sending ProcessScrapedItems response. Processed: %d, Failed: %d", jobID, processed, failed)
	return resp, nil
}
