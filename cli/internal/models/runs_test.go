package models_test

import (
	"encoding/json"
	"testing"

	"github.com/scylladb/argus/cli/internal/models"
	"github.com/stretchr/testify/assert"
	"github.com/stretchr/testify/require"
)

func sctEvents() []models.SCTEvent {
	return []models.SCTEvent{
		{Severity: "ERROR", Message: "long raw error message body", Summary: "short summary"},
		{Severity: "CRITICAL", Message: "event with no summary yet", Summary: ""},
	}
}

// The message column is the last one (see SCTEventsResponse.Headers).
func messageCol(t *testing.T, resp models.SCTEventsResponse) []string {
	t.Helper()
	last := len(resp.Headers()) - 1
	rows := resp.Rows()
	got := make([]string, 0, len(rows))
	for _, r := range rows {
		got = append(got, r[last])
	}
	return got
}

func TestSCTEventsResponse_Rows_SummaryFirstByDefault(t *testing.T) {
	resp := models.SCTEventsResponse{Events: sctEvents()}
	// Summary shown when present; falls back to the message when the summary is empty.
	assert.Equal(t, []string{"short summary", "event with no summary yet"}, messageCol(t, resp))
}

func TestSCTEventsResponse_Rows_RawForcesOriginalMessage(t *testing.T) {
	resp := models.SCTEventsResponse{Events: sctEvents(), Raw: true}
	// --raw shows the original message even when a summary exists.
	assert.Equal(t, []string{"long raw error message body", "event with no summary yet"}, messageCol(t, resp))
}

func TestSCTEventsResponse_JSONCarriesBothMessageAndSummary(t *testing.T) {
	resp := models.SCTEventsResponse{Events: sctEvents()}
	data, err := json.Marshal(resp)
	require.NoError(t, err)

	var out []map[string]any
	require.NoError(t, json.Unmarshal(data, &out))
	require.Len(t, out, 2)
	// JSON is additive: both fields travel regardless of the Raw rendering flag.
	assert.Equal(t, "long raw error message body", out[0]["message"])
	assert.Equal(t, "short summary", out[0]["summary"])
}
