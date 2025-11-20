-- Morning Automation Database Schema for Supabase
-- Run this in Supabase SQL Editor to create the tables

-- Enable UUID extension if needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Content Items Table (podcasts, articles, newsletters)
CREATE TABLE IF NOT EXISTS content_items (
    id SERIAL PRIMARY KEY,
    source_type VARCHAR(50) NOT NULL,
    source_name VARCHAR(255) NOT NULL,
    item_url VARCHAR(1000) NOT NULL UNIQUE,
    title VARCHAR(500) NOT NULL,
    published_date TIMESTAMP,
    description TEXT,
    transcript TEXT,
    youtube_url VARCHAR(500),
    transcript_fetched BOOLEAN DEFAULT FALSE,
    transcript_length INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_source_lookup ON content_items(source_name, item_url);
CREATE INDEX IF NOT EXISTS idx_published ON content_items(published_date);

-- Insights Table (AI-generated content)
CREATE TABLE IF NOT EXISTS insights (
    id SERIAL PRIMARY KEY,
    content_item_id INTEGER NOT NULL,
    insight_text TEXT NOT NULL,
    practical_tips TEXT,
    enriched_content TEXT,
    model_name VARCHAR(50),
    was_test_mode BOOLEAN DEFAULT FALSE,
    token_count INTEGER,
    cost_cents INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for content lookup
CREATE INDEX IF NOT EXISTS idx_content_insights ON insights(content_item_id);

-- Briefings Table (historical archive)
CREATE TABLE IF NOT EXISTS briefings (
    id SERIAL PRIMARY KEY,
    date TIMESTAMP NOT NULL UNIQUE,
    title VARCHAR(255),
    briefing_text TEXT NOT NULL,
    total_episodes INTEGER,
    total_sources INTEGER,
    total_cost_cents INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create index for date lookup
CREATE INDEX IF NOT EXISTS idx_date ON briefings(date);

-- Create updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Add trigger to content_items for auto-updating updated_at
CREATE TRIGGER update_content_items_updated_at 
    BEFORE UPDATE ON content_items
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

