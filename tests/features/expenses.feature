Feature: Double-Entry Expenses
  As a user of the Personal OS
  I want to track income, expenses, and transfers with double-entry accounting
  So that my balances are always accurate and my dashboard reflects true spending

  Scenario: Day-zero setup from Initial Equity does not count as spending
    Given the system equity account is initialized
    And I create a bank account "HDFC Savings" with balance 0
    When I transfer 50000 from Initial Equity to "HDFC Savings"
    Then the "HDFC Savings" account balance should be 50000
    And the monthly spending on the dashboard should be 0
    And the net worth on the dashboard should be 50000

  Scenario: Self-transfer between bank accounts preserves net worth and spending
    Given the system equity account is initialized
    And I create a bank account "HDFC Savings" with balance 0
    And I create a bank account "ICICI Current" with balance 0
    And I transfer 50000 from Initial Equity to "HDFC Savings"
    When I transfer 10000 from "HDFC Savings" to "ICICI Current"
    Then the "HDFC Savings" account balance should be 40000
    And the "ICICI Current" account balance should be 10000
    And the monthly spending on the dashboard should be 0
    And the net worth on the dashboard should be 50000

  Scenario: Direct expense reduces balance and increases monthly spending
    Given the system equity account is initialized
    And I create a bank account "HDFC Savings" with balance 0
    And I transfer 50000 from Initial Equity to "HDFC Savings"
    When I log an expense of 1500 from "HDFC Savings" for "Groceries" category "Food"
    Then the "HDFC Savings" account balance should be 48500
    And the monthly spending on the dashboard should be 1500
    And the category "Food" spending should be 1500
    And the net worth on the dashboard should be 48500
