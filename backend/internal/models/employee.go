package models

import "time"

type Employee struct {
	Skills         	[]string
	YearsOfExperience int
	IndustryExperience int
	Industries []string
	CurrentAllocation float64
	AvailabileFrom 	time.Time
	Certifications  []string
	projectHistory  []string
	Feedback		[]string
	ID int
	Name string
	Role string
		
}