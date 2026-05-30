Feature: Health Check
  As a developer
  I want the application to expose health check endpoints
  So that I can verify the service is running

  Scenario: Root health check returns healthy status
    When I request the root health endpoint
    Then I should receive a 200 status code
    And the response should contain status "healthy"
    And the response should contain app "personal-os"

  Scenario: API v1 health check returns healthy status
    When I request the API v1 health endpoint
    Then I should receive a 200 status code
    And the response should contain status "healthy"
    And the response should contain layer "api"

  Scenario: Web health check returns healthy status
    When I request the web health endpoint
    Then I should receive a 200 status code
    And the response should contain status "healthy"
    And the response should contain layer "web"
