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
    GRPCServerPort string `mapstructure:"GRPC_SERVER_PORT"`

	DefaultSearchLimit int `mapstructure:"DEFAULT_SEARCH_LIMIT"`
}

func LoadConfig(path string) (config Config, err error) {
	if path != "" {
		viper.AddConfigPath(path) 
		viper.SetConfigName("config")   
		viper.SetConfigType("env")      
		
		// Attempt to read the config file
		readErr := viper.ReadInConfig() // Use different variable to avoid shadowing 'err'
		if readErr != nil {
			if _, ok := readErr.(viper.ConfigFileNotFoundError); ok {
				log.Printf("Config file ('config.env') not found in path '%s'. Relying on Environment Variables and Defaults.", path)
				// File not found is okay, proceed
			} else {
				// Different error reading the file (e.g., permissions)
				log.Printf("Warning: Error reading config file '%s': %v. Relying on Environment Variables and Defaults.", viper.ConfigFileUsed(), readErr)
			}
		} else {
            log.Println("Successfully read config file:", viper.ConfigFileUsed())
        }
	} else {
        log.Println("No config file path provided. Relying on Environment Variables and Defaults.")
    }


	viper.AutomaticEnv()

	viper.SetEnvKeyReplacer(strings.NewReplacer(`.`, `_`))

	viper.BindEnv("DBHost", "DB_HOST")
	viper.BindEnv("DBPort", "DB_PORT")
	viper.BindEnv("DBUser", "DB_USER")
	viper.BindEnv("DBPassword", "DB_PASSWORD")
	viper.BindEnv("DBName", "DB_NAME")
	viper.BindEnv("DBSslMode", "DB_SSL_MODE")
	viper.BindEnv("FeatureExtractorAddr", "FEATURE_EXTRACTOR_ADDR")
	viper.BindEnv("ScraperAddr", "SCRAPER_ADDR")
	viper.BindEnv("HTTPServerPort", "HTTP_SERVER_PORT")
	viper.BindEnv("GRPCServerPort", "GRPC_SERVER_PORT")
	viper.BindEnv("DefaultSearchLimit", "DEFAULT_SEARCH_LIMIT")

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
