package models 

import "time"

type approval struct {
	RecommendationID	int
	ApprovedTime time.Time
	ManagerID int
	SelectedEmployeeID int
	SelectedEmployeeName int
	Decision 	string
	Comments string

}