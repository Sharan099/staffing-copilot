package models

import "time"

type StaffingRequest struct {
	ID                       string
	ManagerID                string

	Role                     string
	RequiredSkills           []string
	RequiredExperienceYears  int

	Industry                 string
	Location                 string
	WorkMode                 string

	StartDate                time.Time
	DurationWeeks            int

	Priority                 string

	NumberOfConsultants      int

	RequiredCertifications   []string
}