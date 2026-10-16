import unittest

from scripts.sync_projects import plan


def project(items=()):
    return {
        "id": "p",
        "items": list(items),
        "fields": {
            "Status": {
                "id": "status",
                "options": [
                    {"name": n, "id": n}
                    for n in [
                        "Egiteke",
                        "Lanean",
                        "Berrikusten",
                        "Blokeatuta",
                        "Eginda",
                        "To do",
                        "In Progress",
                        "Done",
                    ]
                ],
            },
            "Taldea": {"id": "team", "options": [{"name": "B-taldea", "id": "B"}]},
            **{
                n: {"id": n}
                for n in ["Hasiera-data", "Amaiera-data", "Start date", "Target date"]
            },
        },
    }


def item(repo="AABD-Ethazi-2627/T2-erronka1", values=None):
    return {
        "id": "i",
        "isArchived": False,
        "content": {
            "__typename": "Issue",
            "id": "issue",
            "repository": {"nameWithOwner": repo},
        },
        "values": values or {},
    }


class SyncTests(unittest.TestCase):
    def test_new_issue_maps_status_and_dates(self):
        changes = plan(
            project(
                [item(values={"Status": "Berrikusten", "Hasiera-data": "2026-10-14"})]
            ),
            project(),
        )
        self.assertEqual(
            changes[0]["values"],
            {
                "Status": {"singleSelectOptionId": "In Progress"},
                "Taldea": {"singleSelectOptionId": "B"},
                "Start date": {"date": "2026-10-14"},
            },
        )
        self.assertIsNone(changes[0]["item_id"])

    def test_second_run_is_noop(self):
        source = project([item(values={"Status": "Eginda"})])
        target = project([item(values={"Status": "Done", "Taldea": "B-taldea"})])
        self.assertEqual(plan(source, target), [])

    def test_foreign_repo_fails_before_mutation(self):
        with self.assertRaises(ValueError):
            plan(project([item(repo="other/repo")]), project())

    def test_unknown_status_fails(self):
        with self.assertRaises(ValueError):
            plan(project([item(values={"Status": "unknown"})]), project())

    def test_draft_fails(self):
        draft = item()
        draft["content"] = {"__typename": "DraftIssue"}
        with self.assertRaises(ValueError):
            plan(project([draft]), project())

    def test_conflicting_team_fails(self):
        with self.assertRaises(ValueError):
            plan(project([item()]), project([item(values={"Taldea": "A-taldea"})]))

    def test_archived_source_is_not_deleted(self):
        archived = item()
        archived["isArchived"] = True
        self.assertEqual(plan(project([archived]), project([item()])), [])

    def test_removed_date_is_cleared(self):
        changes = plan(
            project([item(values={"Status": "Egiteke"})]),
            project(
                [
                    item(
                        values={
                            "Status": "To do",
                            "Taldea": "B-taldea",
                            "Start date": "2026-10-14",
                        }
                    )
                ]
            ),
        )
        self.assertEqual(changes[0]["values"], {"Start date": None})


class IssueFieldTests(unittest.TestCase):
    def test_issue_date_payload_uses_issue_field_id(self):
        from scripts.sync_projects import issue_field_input

        self.assertEqual(
            issue_field_input(
                {"issueField": {"id": "date-id"}}, {"date": "2026-10-14"}
            ),
            {"fieldId": "date-id", "dateValue": "2026-10-14"},
        )

    def test_clear_issue_date(self):
        from scripts.sync_projects import issue_field_input

        self.assertEqual(
            issue_field_input({"issueField": {"id": "date-id"}}, None),
            {"fieldId": "date-id", "delete": True},
        )
