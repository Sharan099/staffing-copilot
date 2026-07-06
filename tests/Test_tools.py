import threading
import unittest

from tools.tools import (
    check_project_history,
    get_availability,
    search_people,
)


class TestTools(unittest.TestCase):
    def test_search_people_matches_all_skills(self):
        results = search_people(["Python", "LLM"])
        self.assertGreater(len(results), 0)
        for employee in results:
            self.assertIn("name", employee)
            self.assertIn("location", employee)

    def test_search_people_extracts_location_from_skills(self):
        results = search_people(["Python", "LLM", "Berlin"])
        self.assertGreater(len(results), 0)
        berlin = [e for e in results if e["location"] == "Berlin"]
        self.assertGreater(len(berlin), 0)

    def test_get_availability_matches_on_or_before_date(self):
        results = get_availability("2026-10-01")
        self.assertGreater(len(results), 0)
        for employee in results:
            self.assertLessEqual(employee["available_from"], "2026-10-01")

    def test_get_availability_rejects_empty_input(self):
        self.assertEqual(get_availability(""), [])
        self.assertEqual(get_availability("   "), [])

    def test_check_project_history_returns_profile(self):
        seed = search_people(["Python", "LLM"])[0]["name"]
        results = check_project_history(seed)
        self.assertGreaterEqual(len(results), 1)
        self.assertEqual(results[0]["name"], seed)
        self.assertIn("skills", results[0])
        self.assertGreater(len(results[0]["skills"]), 0)

    def test_check_project_history_no_match(self):
        results = check_project_history("Nobody")
        self.assertEqual(results, [])

    def test_tools_work_from_worker_thread(self):
        errors = []

        def run_in_thread():
            try:
                search_people(["Python"])
                get_availability("2026-10-01")
                check_project_history("Anna Schwarz")
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=run_in_thread)
        thread.start()
        thread.join()
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
