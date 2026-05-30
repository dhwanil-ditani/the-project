Feature: Bookmarks CRUD
  As a user of the Personal OS
  I want to create, list, retrieve, update, and delete bookmarks
  So that I can organize my saved URLs

  Scenario: Create a bookmark with explicit metadata
    Given I have a bookmark payload with url "https://example.com" and title "Example"
    When I create the bookmark
    Then I should receive a 201 status code
    And the bookmark response should have title "Example"
    And the bookmark response should have url "https://example.com/"

  Scenario: Create a bookmark triggers auto-scraping when title is missing
    Given I have a bookmark payload with url "https://example.com" and no title
    When I create the bookmark
    Then I should receive a 201 status code
    And the bookmark response should have a scraped title

  Scenario: List all bookmarks
    Given there are 3 bookmarks in the database
    When I list all bookmarks
    Then I should receive a 200 status code
    And the response should contain 3 bookmarks

  Scenario: Get a single bookmark by ID
    Given there is a bookmark with url "https://example.com" in the database
    When I get the bookmark by its ID
    Then I should receive a 200 status code
    And the bookmark response should have url "https://example.com/"

  Scenario: Delete a bookmark
    Given there is a bookmark with url "https://example.com" in the database
    When I delete the bookmark by its ID
    Then I should receive a 204 status code
    When I get the bookmark by its ID
    Then I should receive a 404 status code

  Scenario: Create a bookmark with tags
    Given I have a bookmark payload with url "https://example.com" and tags "python, fastapi"
    When I create the bookmark
    Then I should receive a 201 status code
    And the bookmark response should have 2 tags
