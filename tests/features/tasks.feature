Feature: Unified Tasks Engine
  As a user of the Personal OS
  I want the system to lazily evaluate overdue tasks on dashboard access
  So that habits expire, strict tasks stay pending, and new occurrences are spawned

  Scenario: A pending habit from yesterday becomes Missed and next task is spawned
    Given a non-strict recurring rule "Meditate" with daily schedule
    And a pending task "Meditate" linked to that rule due yesterday
    When I load the today dashboard
    Then the original task status should be "Missed"
    And a new pending task "Meditate" should be spawned for the future

  Scenario: A pending strict task from yesterday remains Pending
    Given a strict recurring rule "Bike Service" with monthly schedule
    And a pending task "Bike Service" linked to that rule due yesterday
    When I load the today dashboard
    Then the overdue task "Bike Service" should still be "Pending"

  Scenario: Create a task via the API
    When I create a task with title "Buy groceries" and priority "High"
    Then I should receive a 201 status code
    And the task response should have title "Buy groceries"
    And the task response should have priority "High"

  Scenario: List all tasks
    Given there are 3 tasks in the database
    When I list all tasks
    Then I should receive a 200 status code
    And the response should contain 3 tasks

  Scenario: Create a recurring rule via the API
    When I create a recurring rule "Daily Standup" with rrule "FREQ=DAILY"
    Then I should receive a 201 status code
    And the rule response should have task_title "Daily Standup"

  Scenario: Dashboard returns tasks sorted by priority
    Given a pending high priority task "Urgent Bug" due today
    And a pending low priority task "Nice To Have" due today
    And a pending medium priority task "Code Review" due today
    When I load the today dashboard
    Then the first action item should be "Urgent Bug"
    And the last action item should be "Nice To Have"
