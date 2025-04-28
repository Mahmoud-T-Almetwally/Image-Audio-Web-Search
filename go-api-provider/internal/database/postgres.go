package database

import (
	"fmt"
	"log"
	"os"
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
	"gorm.io/gorm/logger"

	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/config"
	"github.com/Mahmoud-T-Almetwally/Image-Audio-Web-Search/internal/models"
)

func ConnectDB(cfg *config.Config) (*gorm.DB, error) {
	newLogger := logger.New(
		log.New(os.Stdout, "\r\n", log.LstdFlags),
		logger.Config{
			SlowThreshold:             time.Second,
			LogLevel:                  logger.Info,
			IgnoreRecordNotFoundError: true,
			ParameterizedQueries:      true,
			Colorful:                  true,
		},
	)

	log.Printf("Connecting to database with DSN: %s", cfg.DBDSN)

	db, err := gorm.Open(postgres.Open(cfg.DBDSN), &gorm.Config{
		Logger: newLogger,
	})
	if err != nil {
		return nil, fmt.Errorf("failed to connect database: %w", err)
	}

	log.Println("Running database migrations...")
	err = db.AutoMigrate(&models.Image{}, &models.Audio{})
	if err != nil {
		log.Printf("Failed to migrate database schema: %v", err)

	} else {
		log.Println("Database migrations completed.")
	}

	log.Println("Database connection successful.")
	return db, nil
}
