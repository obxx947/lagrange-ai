# ============================================================================
# Lagrange Tactical AI - Ship Search Feature (BDD / Gherkin)
# BDD test scenarios for the ship encyclopedia search and filter functionality.
# ============================================================================

Feature: Ship Search and Filtering
  As a Lagrange fleet commander
  I want to search and filter ships by name, class, tier, and stats
  So that I can quickly find the best ships for my fleet composition

  Background:
    Given the ship database is populated with standard Lagrange ship data
    And the user is on the Ship Encyclopedia page

  # ---- Basic Search ----
  @search @smoke
  Scenario: Search for a ship by exact name
    When the user types "Io" into the search input field
    And the search is triggered
    Then the ship "Io" should be displayed in the results
    And the ship "Ion" should be displayed in the results
    And the ship "Carrier" should not be displayed
    And the result count should show matching ships

  @search
  Scenario: Search for a ship by partial name
    When the user types "storm" into the search input field
    And the search is triggered
    Then all ships with "storm" in their name should be displayed
    And ships without "storm" in their name should be hidden

  @search
  Scenario: Search with no results
    When the user types "zzzznotexist" into the search input field
    And the search is triggered
    Then no ship cards should be displayed
    And an empty state message "No ships match" should be shown

  @search
  Scenario: Clear search returns all ships
    When the user types "Carrier" into the search input field
    And the search is triggered
    And the user clears the search input
    Then all ships should be displayed again
    And the result count should reflect the total ship count

  # ---- Filter by Tier ----
  @filter @tier
  Scenario: Filter ships by Tier 1
    When the user selects "Tier 1" from the tier filter dropdown
    Then only ships with tier equal to 1 should be displayed
    And each displayed ship card should show a "T1" badge

  @filter @tier
  Scenario: Filter ships by Tier 2
    When the user selects "Tier 2" from the tier filter dropdown
    Then only ships with tier equal to 2 should be displayed

  @filter @tier
  Scenario: Filter ships by Tier 3
    When the user selects "Tier 3" from the tier filter dropdown
    Then only ships with tier equal to 3 should be displayed

  @filter @tier
  Scenario: Clear tier filter shows all tiers
    When the user selects "All Tiers" from the tier filter dropdown
    Then ships from all tiers should be displayed

  # ---- Filter by Class ----
  @filter @class
  Scenario: Filter ships by Battle Cruiser class
    When the user selects "Battle Cruiser" from the class filter dropdown
    Then only ships of class "Battle Cruiser" should be displayed

  @filter @class
  Scenario: Filter ships by Carrier class
    When the user selects "Carrier" from the class filter dropdown
    Then only ships of class "Carrier" should be displayed

  @filter @class
  Scenario: Filter ships by Destroyer class
    When the user selects "Destroyer" from the class filter dropdown
    Then only ships of class "Destroyer" should be displayed

  # ---- Combined Filters ----
  @filter @combined
  Scenario: Combine search text with tier filter
    When the user types "cruiser" into the search input field
    And the user selects "Tier 2" from the tier filter dropdown
    Then only Tier 2 ships with "cruiser" in their name or class should be displayed

  @filter @combined
  Scenario: Combine all three filters
    When the user types "battle" into the search input field
    And the user selects "Tier 1" from the tier filter dropdown
    And the user selects "Battle Cruiser" from the class filter dropdown
    Then only Tier 1 Battle Cruisers with "battle" in their metadata should be displayed

  # ---- Sorting ----
  @sort
  Scenario: Sort ships by Hull Points descending
    When the user selects "Sort: Hull Points" from the sort dropdown
    Then the displayed ships should be ordered by HP in descending order
    And the first ship displayed should have the highest HP value

  @sort
  Scenario: Sort ships by Weapon DPS descending
    When the user selects "Sort: Weapon DPS" from the sort dropdown
    Then the displayed ships should be ordered by weapon DPS in descending order

  @sort
  Scenario: Sort ships by Name alphabetically
    When the user selects "Sort: Name A-Z" from the sort dropdown
    Then the displayed ships should be ordered alphabetically by name

  @sort
  Scenario: Sort ships by Speed descending
    When the user selects "Sort: Speed" from the sort dropdown
    Then the displayed ships should be ordered by speed in descending order

  # ---- Pagination ----
  @pagination
  Scenario: Navigate to next page of results
    Given there are more than 20 ships in the database
    When the user clicks the "Page 2" button in the pagination
    Then page 2 ship results should be displayed
    And the "Page 2" button should be marked as active

  @pagination
  Scenario: Pagination preserves active filters
    Given the user has selected "Tier 1" filter
    And there are more Tier 1 ships than one page can display
    When the user clicks the "Page 2" button
    Then only Tier 1 ships should be displayed on page 2

  # ---- Edge Cases ----
  @edge
  Scenario: Search with special characters
    When the user types "X-100" into the search input field
    And the search is triggered
    Then ships matching "X-100" should be correctly displayed
    And no error should occur from special character handling

  @edge
  Scenario: Very long search string is handled gracefully
    When the user types a 500-character string into the search input
    And the search is triggered
    Then the system should not crash or hang
    And the search should complete within 2 seconds

  # ---- Performance ----
  @performance
  Scenario: Search returns results within acceptable time
    Given there are at least 100 ships in the database
    When the user types a search query
    And the search is triggered
    Then the filtered results should be displayed within 500 milliseconds

  @performance
  Scenario: Multiple rapid filter changes do not cause errors
    When the user rapidly changes tier filter 10 times
    Then the UI should remain responsive
    And the final filter state should be correctly applied
