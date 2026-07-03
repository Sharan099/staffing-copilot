package models
import "time"
type CandidateRecommendation struct {
    EmployeeID       int
	EmployeeName 	string
    AvailableFrom    time.Time
    Location         string
    ConfidenceScore  float64
    RiskScore        int
    Rank             int
    Reasons          []string
	Summary 		string
}