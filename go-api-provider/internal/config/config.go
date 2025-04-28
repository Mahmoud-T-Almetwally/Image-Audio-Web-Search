package config

import (
	"fmt"
	"github.com/spf13/viper"
	"log"
	"strings"
)

type Config struct {
	DBHost     string `mapstructure:"DB_HOST"`
	DBPort     string `mapstructure:"DB_PORT"`
	DBUser     string `mapstructure:"DB_USER"`
	DBPassword string `mapstructure:"DB_PASSWORD"`
	DBName     string `mapstructure:"DB_NAME"`
	DBSslMode  string `mapstructure:"DB_SSL_MODE"`
	DBDSN      string

	FeatureExtractorAddr string `mapstructure:"FEATURE_EXTRACTOR_ADDR"`
	ScraperAddr          string `mapstructure:"SCRAPER_ADDR"`

	HTTPServerPort string `mapstructure:"HTTP_SERVER_PORT"`

	DefaultSearchLimit int `mapstructure:"DEFAULT_SEARCH_LIMIT"`
}

func LoadConfig(path string) (config Config, err error) {
	viper.AddConfigPath(path)
	viper.SetConfigName("config")
	viper.SetConfigType("env")

	viper.AutomaticEnv()

	viper.SetEnvKeyReplacer(strings.NewReplacer(`.`, `_`))

	viper.SetDefault("HTTP_SERVER_PORT", "8080")
	viper.SetDefault("DB_SSL_MODE", "disable")
	viper.SetDefault("DEFAULT_SEARCH_LIMIT", 10)
	viper.SetDefault("FEATURE_EXTRACTOR_ADDR", "localhost:50051")
	viper.SetDefault("SCRAPER_ADDR", "localhost:50052")

	err = viper.ReadInConfig()
	if err != nil {
		if _, ok := err.(viper.ConfigFileNotFoundError); ok {
			log.Println("Config file not found, using environment variables and defaults.")

			err = nil
		} else {

			log.Printf("Error reading config file: %s\n", err)
			return
		}
	}

	err = viper.Unmarshal(&config)
	if err != nil {
		log.Printf("Unable to decode config into struct: %v\n", err)
		return
	}

	config.DBDSN = fmt.Sprintf("host=%s port=%s user=%s password=%s dbname=%s sslmode=%s",
		config.DBHost, config.DBPort, config.DBUser, config.DBPassword, config.DBName, config.DBSslMode)

	log.Println("Configuration loaded successfully")
	return
}
