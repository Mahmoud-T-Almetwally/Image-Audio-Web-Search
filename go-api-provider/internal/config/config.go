package config

import (
	"fmt"
	"log"
	"os"
	"github.com/joho/godotenv"
)

type Config struct {
	DBHost     string
	DBPort     string
	DBUser     string
	DBPassword string
	DBName     string
	DBSslMode  string
	DBDSN      string

	FeatureExtractorAddr string
	ScraperAddr          string

	HTTPServerPort string
	GRPCServerPort string

	DefaultSearchLimit int
}

func LoadConfig(path string) (config Config, err error) {
	// Load environment variables from the given file (e.g., "../../config.env")
	if path != "" {
		err = godotenv.Load(path)
		if err != nil {
			log.Printf("Warning: could not load env file at %s: %v", path, err)
		}
	} else {
		_ = godotenv.Load()
		log.Println("No config file path provided. Relying on Environment Variables and Defaults.")
	}

	config.DBHost = os.Getenv("DB_HOST")
	config.DBPort = os.Getenv("DB_PORT")
	config.DBUser = os.Getenv("DB_USER")
	config.DBPassword = os.Getenv("DB_PASSWORD")
	config.DBName = os.Getenv("DB_NAME")
	config.DBSslMode = os.Getenv("DB_SSL_MODE")
	config.FeatureExtractorAddr = os.Getenv("FEATURE_EXTRACTOR_ADDR")
	config.ScraperAddr = os.Getenv("SCRAPER_ADDR")
	config.HTTPServerPort = os.Getenv("HTTP_SERVER_PORT")
	config.GRPCServerPort = os.Getenv("GRPC_SERVER_PORT")

	if v := os.Getenv("DEFAULT_SEARCH_LIMIT"); v != "" {
		fmt.Sscanf(v, "%d", &config.DefaultSearchLimit)
	} else {
		config.DefaultSearchLimit = 3
	}

	config.DBDSN = fmt.Sprintf(
		"host=%s port=%s user=%s password=%s dbname=%s sslmode=%s",
		config.DBHost, config.DBPort, config.DBUser, config.DBPassword, config.DBName, config.DBSslMode,
	)

	log.Printf("connecting to host=%s port=%s user=%s password=%s dbname=%s sslmode=%s",
		config.DBHost, config.DBPort, config.DBUser, config.DBPassword, config.DBName, config.DBSslMode,)

	return
}
