Feature: Personal Knowledge Base
  As a user of the Personal OS
  I want to create notes with wiki-links that auto-create placeholder notes
  So that my knowledge graph stays connected and navigable

  Scenario: Creating a note with a wiki-link auto-creates the target note and graph edge
    When I create a note "Project Ideas" with content "Check out [[New Idea]] and [[Research Topics]]"
    Then I should receive a 201 status code
    And a note titled "New Idea" should exist as a placeholder
    And a note titled "Research Topics" should exist as a placeholder
    And the graph should have 3 nodes
    And the graph should have 2 edges
    And there should be an edge from "Project Ideas" to "New Idea"
    And there should be an edge from "Project Ideas" to "Research Topics"

  Scenario: Updating a note to remove a wiki-link removes the edge
    Given a note "Daily Log" with content "Worked on [[Feature A]] and [[Feature B]]"
    When I update note "Daily Log" with content "Worked on [[Feature A]] only"
    Then the graph should have 3 nodes
    And the graph should have 1 edges
    And there should be an edge from "Daily Log" to "Feature A"
    And there should be no edge from "Daily Log" to "Feature B"

  Scenario: Create and list notes
    Given a note "Note One" with content "First note"
    And a note "Note Two" with content "Second note"
    When I list all notes
    Then the response should contain 2 notes
