package utils

import (
	"regexp"
	"strconv"
	"time"
)

func CalculateTimeAgo(timespan string) (time.Time, error) {
	re := regexp.MustCompile(`(\d+[yMdhms])`)
	matches := re.FindAllString(timespan, -1)

	endTime := time.Now()

	years, months, days := 0, 0, 0
	var duration time.Duration

	for _, match := range matches {
		unit := match[len(match)-1]
		value, _ := strconv.Atoi(match[:len(match)-1])

		switch unit {
		case 'y':
			years += value
		case 'M':
			months += value
		case 'd':
			days += value
		case 'h':
			duration += time.Duration(value) * time.Hour
		case 'm':
			duration += time.Duration(value) * time.Minute
		case 's':
			duration += time.Duration(value) * time.Second
		}
	}

	startTime := endTime.AddDate(-years, -months, -days)
	startTime = startTime.Add(-duration)

	return startTime, nil
}
