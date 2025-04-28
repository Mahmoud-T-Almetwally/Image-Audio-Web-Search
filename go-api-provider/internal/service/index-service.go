package service

import (
	"context"
	"fmt"
	"log"
	"mime/multipart"
	"os"

	"github.com/google/uuid"

	// "net/http"
	"runtime"
	"strings"

	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client"
	fpb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/featurepb"
	ipb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/indexingpb"
	spb "github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/client/scrapepb"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/config"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/database"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/models"
	"golang.org/x/sync/errgroup"
)

func (s *IndexService) HandleScrapedBatch(ctx context.Context, batchItems []*ipb.ScrapedItem, jobID string) (processedCount, failedCount int, err error) {
	itemCount := len(batchItems)
	log.Printf("[Job %s] IndexService: Handling batch of %d scraped items", jobID, itemCount)

    // Use an errgroup for concurrent processing
    // Limit concurrency to avoid overwhelming FE service or DB
    // Adjust limit based on resources
    concurrencyLimit := runtime.GOMAXPROCS(0) * 2 
    g, childCtx := errgroup.WithContext(ctx)
    g.SetLimit(concurrencyLimit) 

    processedChan := make(chan bool, itemCount) // Channel to count successes
    failedChan := make(chan bool, itemCount)   // Channel to count failures

	for _, item := range batchItems {
        // Capture item in loop variable for goroutine
        currentItem := item 

		g.Go(func() error {
            // Use childCtx which cancels if any goroutine returns an error
			err := s.processSingleScrapedItem(childCtx, currentItem)
			if err != nil {
				log.Printf("[Job %s] Failed processing item (Page: %s, Media: %s): %v", jobID, currentItem.PageUrl, currentItem.MediaUrl, err)
                failedChan <- true // Signal failure
				// Decide if one failure should cancel the whole batch (by returning err)
                // For now, let's log and continue processing others
                // return fmt.Errorf("failed processing item for page %s: %w", currentItem.PageUrl, err) 
                return nil // Don't cancel group on single item failure
			} else {
                processedChan <- true // Signal success
            }
            return nil
		})
	}

    // Wait for all goroutines to finish
    groupErr := g.Wait()

    // Close channels and count results
    close(processedChan)
    close(failedChan)
    for range processedChan { processedCount++ }
    for range failedChan { failedCount++ }

    log.Printf("[Job %s] Batch processing finished. Processed: %d, Failed: %d", jobID, processedCount, failedCount)
    
    // Return the error from the errgroup if any goroutine failed critically (if we chose to return errors)
    if groupErr != nil {
        return processedCount, failedCount, fmt.Errorf("error during batch processing: %w", groupErr)
    }
    return processedCount, failedCount, nil
}

func (s *IndexService) processSingleScrapedItem(ctx context.Context, item *ipb.ScrapedItem) error {
    pageURL := item.PageUrl
    mediaURL := item.MediaUrl
    
    // 1. Map Proto MediaType to internal Model MediaType
    var modelMediaType models.MediaType
    var featureProtoMediaType fpb.MediaType
    switch item.MediaType {
    case ipb.MediaType_IMAGE:
        modelMediaType = models.ImageType
        featureProtoMediaType = fpb.MediaType_IMAGE
    case ipb.MediaType_AUDIO:
        modelMediaType = models.AudioType
        featureProtoMediaType = fpb.MediaType_AUDIO
    default:
        return fmt.Errorf("unsupported media type enum value: %v", item.MediaType)
    }

    // 2. Check if PageURL already exists in DB (Deduplication)
    exists, err := s.repo.CheckPageURLExists(ctx, pageURL, modelMediaType)
    if err != nil {
        // Log error but potentially continue if DB check fails? Or fail item? Fail for now.
        return fmt.Errorf("database check failed for page %s: %w", pageURL, err)
    }
    if exists {
        log.Printf("Skipping already indexed page URL: %s (Type: %s)", pageURL, modelMediaType)
        return nil // Not an error, just skip
    }

    // 3. Prepare request for Feature Extractor
    feItems := []*fpb.UrlItem{
        {
            MediaUrl: mediaURL,          // URL for FE to download/process
            Type:     featureProtoMediaType,
            PageUrl:  pageURL,           // URL to associate with the vector
        },
    }

    // 4. Call Feature Extractor (for this single item)
    //    Optimization: Could collect items here and make batched calls to FE too.
    feRes, err := s.featureExtr.ProcessUrls(ctx, feItems, false) // Denoising false for scraped items? Configurable?
    if err != nil {
        return fmt.Errorf("feature extraction gRPC call failed for media %s: %w", mediaURL, err)
    }

    // 5. Process FE Response
    if len(feRes.Results) != 1 {
        return fmt.Errorf("unexpected FE result count (%d) for media %s", len(feRes.Results), mediaURL)
    }
    result := feRes.Results[0]

    if result.Status != fpb.Status_SUCCESS {
        return fmt.Errorf("feature extraction failed for media %s: Status=%s, Msg=%s", mediaURL, result.Status, result.ErrorMessage)
    }
    if len(result.FeatureVector) == 0 {
        return fmt.Errorf("feature extraction succeeded but returned empty vector for media %s", mediaURL)
    }

    // 6. Deserialize vector
    vector, err := client.VectorFromBytes(result.FeatureVector)
    if err != nil {
        return fmt.Errorf("failed to deserialize feature vector for media %s: %w", mediaURL, err)
    }

    // 7. Save to DB (associating with PageURL)
    log.Printf("Saving vector for page URL: %s (Type: %s)", pageURL, modelMediaType)
    switch modelMediaType {
    case models.ImageType:
        err = s.repo.InsertImage(ctx, pageURL, vector)
    case models.AudioType:
        err = s.repo.InsertAudio(ctx, pageURL, vector)
    }
    if err != nil {
        return fmt.Errorf("database insert failed for page %s: %w", pageURL, err)
    }

    log.Printf("Successfully processed and saved item for page: %s", pageURL)
    return nil // Success for this item
}

type IndexService struct {
	repo        database.MediaRepository
	scraper     *client.ScraperClient
	featureExtr *client.FeatureExtractorClient
	cfg *config.Config
}

func NewIndexService(repo database.MediaRepository, sc *client.ScraperClient, fe *client.FeatureExtractorClient, cfg *config.Config) *IndexService {
	return &IndexService{
		repo:        repo,
		scraper:     sc,
		featureExtr: fe,
		cfg:         cfg,
	}
}

func (s *IndexService) RequestScrape(ctx context.Context, req models.ScrapeRequest) (string, string, error) {
	log.Printf("IndexService: Received request to scrape URL: %s", req.URL)

	if req.DepthLimit <= 0 {
		req.DepthLimit = 2
	}
	if req.CrawlStrategy == "" {
		req.CrawlStrategy = "default"
	}

	res, err := s.scraper.StartScrape(
		ctx,
		req.URL,
		req.AllowedDomains,
		int32(req.DepthLimit),
		req.CrawlStrategy,
		req.UsePlaywright,
	)
	if err != nil {
		return "", "REJECTED", fmt.Errorf("failed to start scrape job: %w", err)
	}

	if res.Status == spb.Status_REJECTED {
		return res.JobId, "REJECTED", fmt.Errorf("scrape job rejected by scraper service: %s", res.Message)
	}

	return res.JobId, "ACCEPTED", nil
}

func (s *IndexService) IndexDirectMedia(ctx context.Context, fileHeader *multipart.FileHeader, pageURL *string) error {
	log.Printf("IndexService: Received request to index direct media: %s", fileHeader.Filename)

	contentType := fileHeader.Header.Get("Content-Type")
	mediaType, err := determineMediaType(contentType, fileHeader.Filename)
	if err != nil {
		return fmt.Errorf("cannot determine media type: %w", err)
	}

	// mediaURL, err := s.uploadMediaAndGetURL(ctx, fileHeader)
	
	if err != nil {
		return fmt.Errorf("failed to handle media upload: %w", err)
	}

	var protoMediaType fpb.MediaType
	switch mediaType {
	case models.ImageType:
		protoMediaType = fpb.MediaType_IMAGE
	case models.AudioType:
		protoMediaType = fpb.MediaType_AUDIO
	default:
		return fmt.Errorf("internal error: unhandled media type: %s", mediaType)
	}

	localFilePath, mediaURL, err := saveTempMediaAndGetURL(fileHeader, s.cfg.TempMediaDir, s.cfg.APIBaseURL)

	if err != nil {
		return fmt.Errorf("failed to save temporary media: %w", err)
	}

	defer func() {
		log.Printf("Attempting cleanup of temporary file: %s", localFilePath)
		err := os.Remove(localFilePath)
		if err != nil && !os.IsNotExist(err) { // Log error only if it's not "already deleted"
			log.Printf("Error deleting temporary file %s: %v", localFilePath, err)
		} else if err == nil {
			log.Printf("Successfully deleted temporary file: %s", localFilePath)
		}
	}()


	dbURL := mediaURL
	if pageURL != nil && *pageURL != "" {
		dbURL = *pageURL
	}

	itemsToProcess := []*fpb.UrlItem{
		{ MediaUrl: mediaURL, Type: protoMediaType, PageUrl: dbURL },
	}


	feRes, err := s.featureExtr.ProcessUrls(ctx, itemsToProcess, false)
	if err != nil {

		return fmt.Errorf("feature extraction failed: %w", err)
	}

	if len(feRes.Results) != 1 {

		return fmt.Errorf("unexpected number of results from feature extractor: %d", len(feRes.Results))
	}
	result := feRes.Results[0]

	if result.Status != fpb.Status_SUCCESS {

		return fmt.Errorf("feature extraction reported failure: Status=%s, Msg=%s", result.Status, result.ErrorMessage)
	}
	if len(result.FeatureVector) == 0 {

		return fmt.Errorf("feature extraction succeeded but returned empty vector")
	}

	vector, err := client.VectorFromBytes(result.FeatureVector)
	if err != nil {
		return fmt.Errorf("failed to deserialize feature vector: %w", err)
	}

	log.Printf("Saving extracted vector for URL: %s (Type: %s)", dbURL, mediaType)
	switch mediaType {
	case models.ImageType:
		err = s.repo.InsertImage(ctx, dbURL, vector)
	case models.AudioType:
		err = s.repo.InsertAudio(ctx, dbURL, vector)
	}
	if err != nil {

		return fmt.Errorf("failed to save vector to database: %w", err)
	}

	log.Printf("Successfully indexed direct media for URL: %s", dbURL)
	return nil
}

func (s *IndexService) uploadMediaAndGetURL(ctx context.Context, fileHeader *multipart.FileHeader) (string, error) {

	file, err := fileHeader.Open()
	if err != nil {
		return "", fmt.Errorf("failed to open uploaded file: %w", err)
	}
	defer file.Close()

	log.Printf("[Placeholder] Uploaded %s to temporary storage.", fileHeader.Filename)

	return fmt.Sprintf("http://temp-storage.example.com/%s/%s", uuid.NewString(), fileHeader.Filename), nil 

}

func determineMediaType(contentType, filename string) (models.MediaType, error) {

	if strings.HasPrefix(contentType, "image/") {
		return models.ImageType, nil
	}
	if strings.HasPrefix(contentType, "audio/") {
		return models.AudioType, nil
	}

	lowerFilename := strings.ToLower(filename)
	for _, ext := range []string{".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp", ".tiff"} {
		if strings.HasSuffix(lowerFilename, ext) {
			return models.ImageType, nil
		}
	}
	for _, ext := range []string{".mp3", ".wav", ".ogg", ".m4a", ".flac", ".aac"} {
		if strings.HasSuffix(lowerFilename, ext) {
			return models.AudioType, nil
		}
	}

	return "", fmt.Errorf("could not determine media type from Content-Type '%s' or filename '%s'", contentType, filename)
}
