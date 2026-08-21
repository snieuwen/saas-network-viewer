import unittest

import pandas as pd

from scenario_analysis import Scenario
from user_analysis import (
    scenario_user_summary,
    selection_user_summary,
    user_assignment_rows,
)


class UserAnalysisTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            [
                {"USER_LOGIN_HASH": "U1", "ROLE_CODE": "R1", "PRIVILEGE": "P1"},
                {"USER_LOGIN_HASH": "U1", "ROLE_CODE": "R1", "PRIVILEGE": "P2"},
                {"USER_LOGIN_HASH": "U1", "ROLE_CODE": "R2", "PRIVILEGE": "P1"},
                {"USER_LOGIN_HASH": "U2", "ROLE_CODE": "R1", "PRIVILEGE": "P1"},
                {"USER_LOGIN_HASH": "U3", "ROLE_CODE": "R3", "PRIVILEGE": "P3"},
            ]
        )

    def test_selection_requires_every_selected_node(self) -> None:
        result = selection_user_summary(
            self.frame, ["role:R2", "privilege:P2"], total_frame=self.frame
        )
        self.assertEqual(result["USER"].tolist(), ["U1"])
        self.assertEqual(int(result.iloc[0]["TOTAL_RELATIONSHIPS"]), 3)

    def test_scenario_user_statuses_distinguish_affected_and_removed(self) -> None:
        scenario = Scenario("Test", "SKU", "Service", excluded_roles=["R1", "R3"])
        result = scenario_user_summary(self.frame, scenario).set_index("USER")
        self.assertEqual(result.loc["U1", "STATUS"], "Affected")
        self.assertEqual(result.loc["U2", "STATUS"], "Removed from scope")
        self.assertEqual(result.loc["U3", "STATUS"], "Removed from scope")

    def test_assignment_rows_explain_exact_pair_exclusion(self) -> None:
        scenario = Scenario("Test", "SKU", "Service")
        scenario.add_privilege_roles("P1", ["R2"])
        result = user_assignment_rows(self.frame, "U1", scenario)
        excluded = result[result["STATUS"].eq("Excluded")]
        self.assertEqual(len(excluded), 1)
        self.assertEqual(excluded.iloc[0]["REASON"], "Privilege excluded from role")


if __name__ == "__main__":
    unittest.main()
