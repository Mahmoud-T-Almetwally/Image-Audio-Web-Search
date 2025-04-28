package service

import (
	"fmt"
	"io"
	"log"
	"mime"
	"mime/multipart"
	"net/url"
	"os"
	"path/filepath"

	"github.com/google/uuid"
)

func saveTempMediaAndGetURL(
	fileHeader *multipart.FileHeader,
	tempDir string,
	apiBaseURL string,
) (localFilePath string, fileURL string, err error) {

	ext := filepath.Ext(fileHeader.Filename)
	if ext == "" {

		contentType := fileHeader.Header.Get("Content-Type")
		extensions, _ := mime.ExtensionsByType(contentType)
		if len(extensions) > 0 {
			ext = extensions[0]
		} else {
			ext = ".tmp"
			log.Printf("Warning: Could not determine extension for file %s (type: %s), using .tmp", fileHeader.Filename, contentType)
		}
	}
	uniqueFilename := fmt.Sprintf("%s%s", uuid.NewString(), ext)

	localFilePath = filepath.Join(tempDir, uniqueFilename)

	srcFile, err := fileHeader.Open()
	if err != nil {
		return "", "", fmt.Errorf("failed to open uploaded file: %w", err)
	}
	defer srcFile.Close()

	dstFile, err := os.Create(localFilePath)
	if err != nil {
		return "", "", fmt.Errorf("failed to create temp file %s: %w", localFilePath, err)
	}
	defer dstFile.Close()

	_, err = io.Copy(dstFile, srcFile)
	if err != nil {

		os.Remove(localFilePath)
		return "", "", fmt.Errorf("failed to copy content to temp file %s: %w", localFilePath, err)
	}

	err = dstFile.Sync()
	if err != nil {
		log.Printf("Warning: Failed to sync temp file %s to disk: %v", localFilePath, err)

	}

	fileURL, err = url.JoinPath(apiBaseURL, "/temp_media/", uniqueFilename)
	if err != nil {

		return localFilePath, "", fmt.Errorf("failed to construct file URL: %w", err)
	}

	log.Printf("Saved temp file: %s, URL: %s", localFilePath, fileURL)
	return localFilePath, fileURL, nil
}
