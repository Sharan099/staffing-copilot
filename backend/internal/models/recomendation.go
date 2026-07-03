package models

import "time"

type Recommendation struct {
	RequestID		 int
	GeneratedAt		time.Time
	Candidates		[]CandidateRecommendation
	
}