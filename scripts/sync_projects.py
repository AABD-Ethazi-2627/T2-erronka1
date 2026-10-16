"""Reconcile B-taldea Project #2 into #1; dry-run unless --apply."""

import argparse
import json
import os
import subprocess

ORG = "AABD-Ethazi-2627"
REPO = f"{ORG}/T2-erronka1"
STATUS = {
    "Egiteke": "Todo",
    "Lanean": "In Progress",
    "Berrikusten": "In Progress",
    "Blokeatuta": "In Progress",
    "Eginda": "Done",
}


def graphql(query, **variables):
    result = subprocess.run(
        ["gh", "api", "graphql", "--input", "-"],
        input=json.dumps({"query": query, "variables": variables}),
        text=True,
        capture_output=True,
        check=False,
        timeout=90,
    )
    if result.returncode:
        raise RuntimeError(
            "GitHub API request failed; check authentication and permissions"
        )
    response = json.loads(result.stdout)
    if response.get("errors"):
        raise RuntimeError(
            "GitHub GraphQL returned errors; no further writes attempted"
        )
    return response["data"]


def read_project(number):
    query = """query($org:String!, $number:Int!, $cursor:String) {
      organization(login:$org) { projectV2(number:$number) { id
        fields(first:100) { pageInfo { hasNextPage } nodes {
          ... on ProjectV2Field { id name dataType isIssueField issueField { ... on IssueFieldDate { id name } } }
          ... on ProjectV2SingleSelectField { id name options { id name } }
        } }
        items(first:100, after:$cursor) { pageInfo { hasNextPage endCursor } nodes {
          id isArchived content { __typename
            ... on Issue { id repository { nameWithOwner } }
            ... on PullRequest { id repository { nameWithOwner } }
          }
          fieldValues(first:100) { pageInfo { hasNextPage } nodes {
            ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2FieldCommon { name } } }
            ... on ProjectV2ItemFieldDateValue { date field { ... on ProjectV2FieldCommon { name } } }
            ... on ProjectV2ItemIssueFieldValue { field { ... on ProjectV2FieldCommon { name } } issueFieldValue { ... on IssueFieldDateValue { value } } }
          } }
        } }
      } }
    }"""
    items, cursor = [], None
    while True:
        project = graphql(query, org=ORG, number=number, cursor=cursor)["organization"][
            "projectV2"
        ]
        if not project or project["fields"]["pageInfo"]["hasNextPage"]:
            raise ValueError("Project unavailable or more than 100 fields; aborting")
        for item in project["items"]["nodes"]:
            if item["fieldValues"]["pageInfo"]["hasNextPage"]:
                raise ValueError("Incomplete item fields; aborting")
            item["values"] = {
                v["field"]["name"]: v.get("issueFieldValue", {}).get("value")
                if v.get("issueFieldValue")
                else v.get("date", v.get("name"))
                for v in item["fieldValues"]["nodes"]
                if "field" in v
            }
            items.append(item)
        page = project["items"]["pageInfo"]
        if not page["hasNextPage"]:
            break
        cursor = page["endCursor"]
    return {
        "id": project["id"],
        "fields": {f["name"]: f for f in project["fields"]["nodes"] if f},
        "items": items,
    }


def option(field, name):
    matches = [o["id"] for o in field["options"] if o["name"] == name]
    if len(matches) != 1:
        raise ValueError(f"Unknown or ambiguous option: {name}")
    return matches[0]


def source_date(values, primary, fallback):
    if (
        values.get(primary)
        and values.get(fallback)
        and values[primary] != values[fallback]
    ):
        raise ValueError(f"Conflicting dates: {primary}/{fallback}")
    return values.get(primary) or values.get(fallback)


def plan(source, target):
    # Validate the complete plan before the first mutation.
    for name in ["Status", "Taldea", "Start date", "Target date"]:
        if name not in target["fields"]:
            raise ValueError(f"Missing central field: {name}")
    existing = {}
    for item in target["items"]:
        content = item.get("content")
        if content and content.get("id"):
            if content["id"] in existing:
                raise ValueError("Duplicate central content")
            existing[content["id"]] = item
    changes = []
    for item in source["items"]:
        if item["isArchived"]:
            continue
        content = item.get("content")
        if not content or content.get("__typename") not in ("Issue", "PullRequest"):
            raise ValueError(
                "Use repository issues/PRs instead of draft or inaccessible items"
            )
        if content["repository"]["nameWithOwner"] != REPO:
            raise ValueError(f"Source contains content outside {REPO}")
        values = item["values"]
        if values.get("Taldea") not in (None, "B-taldea"):
            raise ValueError("Source team conflicts with B-taldea")
        previous = existing.get(content["id"])
        if previous and (
            previous["isArchived"]
            or previous["values"].get("Taldea") not in (None, "B-taldea")
        ):
            raise ValueError("Central item archived or assigned to another team")
        current = previous["values"] if previous else {}
        name = values.get("Status")
        if name is not None and name not in STATUS:
            raise ValueError(f"Unknown source status: {name}")
        desired = {
            "Status": STATUS.get(name),
            "Taldea": "B-taldea",
            "Start date": source_date(values, "Hasiera-data", "Start date"),
            "Target date": source_date(values, "Amaiera-data", "Target date"),
        }
        updates = {}
        for field, value in desired.items():
            if current.get(field) == value:
                continue
            if value is None:
                updates[field] = None
            elif field in ("Status", "Taldea"):
                updates[field] = {
                    "singleSelectOptionId": option(target["fields"][field], value)
                }
            else:
                updates[field] = {"date": value}
        if updates or previous is None:
            changes.append(
                {
                    "content_id": content["id"],
                    "item_id": previous["id"] if previous else None,
                    "values": updates,
                }
            )
    return changes


def issue_field_input(field, value):
    payload = {"fieldId": field["issueField"]["id"]}
    payload.update({"delete": True} if value is None else {"dateValue": value["date"]})
    return payload


def apply(target, changes):
    for change in changes:
        item_id = change["item_id"]
        if item_id is None:
            item_id = graphql(
                """mutation($project:ID!, $content:ID!) {
              addProjectV2ItemById(input:{projectId:$project, contentId:$content}) { item { id } }
            }""",
                project=target["id"],
                content=change["content_id"],
            )["addProjectV2ItemById"]["item"]["id"]
        for name, value in change["values"].items():
            variables = {
                "project": target["id"],
                "item": item_id,
                "field": target["fields"][name]["id"],
            }
            if target["fields"][name].get("isIssueField"):
                graphql(
                    """mutation($issue:ID!, $field:IssueFieldCreateOrUpdateInput!) {
                  updateIssueFieldValue(input:{issueId:$issue,issueField:$field}) { clientMutationId }
                }""",
                    issue=change["content_id"],
                    field=issue_field_input(target["fields"][name], value),
                )
            elif value is None:
                graphql(
                    """mutation($project:ID!, $item:ID!, $field:ID!) {
                  clearProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field}) { projectV2Item { id } }
                }""",
                    **variables,
                )
            else:
                graphql(
                    """mutation($project:ID!, $item:ID!, $field:ID!, $value:ProjectV2FieldValue!) {
                  updateProjectV2ItemFieldValue(input:{projectId:$project,itemId:$item,fieldId:$field,value:$value}) { projectV2Item { id } }
                }""",
                    **variables,
                    value=value,
                )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    source, target = read_project(2), read_project(1)
    changes = plan(source, target)
    summary = f"Project #2 -> #1: {len(changes)} items need changes; apply={args.apply}"
    print(summary)
    if args.apply:
        apply(target, changes)
        if plan(read_project(2), read_project(1)):
            raise RuntimeError(
                "Projects changed during sync or verification failed; rerun"
            )
        print("Verified: no remaining differences in managed fields")
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as report:
            report.write(summary + "\n")


if __name__ == "__main__":
    main()
