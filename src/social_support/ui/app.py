"""Streamlit UI. Run with: ``uv run streamlit run src/social_support/ui/app.py``"""

import streamlit as st

from social_support.ui.client import ApiClient, ApiError

EMPLOYMENT_STATUSES = {
    "EMPLOYED": "Employed",
    "SELF_EMPLOYED": "Self-employed",
    "UNEMPLOYED": "Unemployed",
    "STUDENT": "Student",
    "RETIRED": "Retired",
}
OUTCOMES = {  # label, badge colour
    "APPROVE": ("Approve", "green"),
    "NEEDS_HUMAN_REVIEW": ("Needs Human Review", "orange"),
    "SOFT_DECLINE": ("Soft Decline", "gray"),
}
INCOME_HELP = (
    "Net (take-home) monthly income from all sources (salary, business, rental, pensions, "
    "existing benefits) for all household members"
)


@st.cache_resource
def get_client() -> ApiClient:
    return ApiClient()


def _submit_application() -> None:
    """Form callback: runs before the rerun, so results render on the same screen."""
    state = st.session_state
    payload = {
        "full_name": state.full_name,
        "emirates_id": state.emirates_id,
        "family_size": int(state.family_size),
        "net_monthly_income_aed": f"{state.net_monthly_income_aed:.2f}",
        "employment_status": state.employment_status,
    }
    state.apply_result, state.apply_errors, state.apply_failure = None, {}, None
    try:
        state.apply_result = get_client().submit(payload)
    except ApiError as exc:
        if exc.field_errors:
            state.apply_errors = exc.field_errors
        else:
            state.apply_failure = exc.detail


def _field_error(field: str) -> None:
    message = st.session_state.get("apply_errors", {}).get(field)
    if message:
        st.markdown(f":red[{message}]")


def _lookup_application() -> None:
    state = st.session_state
    state.lookup_result, state.lookup_failure = None, None
    try:
        state.lookup_result = get_client().lookup(state.lookup_reference, state.lookup_emirates_id)
    except ApiError as exc:
        state.lookup_failure = exc.detail


def _show_decision(result: dict, *, show_reference_hint: bool = True) -> None:
    decision = result["decision"]
    label, colour = OUTCOMES[decision["outcome"]]
    st.subheader("Recommendation")
    st.badge(label, color=colour)
    st.markdown(decision["explanation"])
    if decision["suggested_next_steps"]:
        st.markdown("**Suggested next steps**")
        st.markdown("\n".join(f"- {step}" for step in decision["suggested_next_steps"]))
    if show_reference_hint:
        st.markdown(
            f"Reference number: **{result['reference_number']}**. Keep it to look up this "
            "application later."
        )
    if result["previous_application_exists"]:
        st.info("A previous application exists for this Emirates ID.")


def render_apply(client: ApiClient) -> None:
    st.caption("Use synthetic data only. Do not enter real personal information.")
    with st.form("apply"):
        st.text_input("Full name", key="full_name")
        _field_error("full_name")
        st.text_input("Emirates ID", key="emirates_id", placeholder="784-YYYY-NNNNNNN-N")
        _field_error("emirates_id")
        st.number_input("Family size (including the applicant)", key="family_size", value=1, step=1)
        _field_error("family_size")
        st.number_input(
            "Net monthly household income (AED)",
            key="net_monthly_income_aed",
            value=0.0,
            step=100.0,
            format="%.2f",
            help=INCOME_HELP,
        )
        st.caption(f"{INCOME_HELP}.")  # FR-001: visible, not only on hover
        _field_error("net_monthly_income_aed")
        st.selectbox(
            "Employment status",
            options=list(EMPLOYMENT_STATUSES),
            format_func=EMPLOYMENT_STATUSES.get,
            key="employment_status",
        )
        _field_error("employment_status")
        st.form_submit_button("Submit application", on_click=_submit_application)

    if st.session_state.get("apply_failure"):
        st.error(st.session_state.apply_failure)
    if st.session_state.get("apply_result"):
        _show_decision(st.session_state.apply_result)


def render_lookup(client: ApiClient) -> None:
    st.caption("Enter the reference number together with the applicant's Emirates ID.")
    with st.form("lookup"):
        st.text_input("Reference number", key="lookup_reference", placeholder="SSA-XXXXXXXXXX")
        st.text_input("Emirates ID", key="lookup_emirates_id", placeholder="784-YYYY-NNNNNNN-N")
        st.form_submit_button("Look up", on_click=_lookup_application)

    if st.session_state.get("lookup_failure"):
        st.error(st.session_state.lookup_failure)
    result = st.session_state.get("lookup_result")
    if result:
        application = result["application"]
        decision = result["decision"]
        st.subheader(f"Application {result['reference_number']}")
        st.markdown(
            "\n".join(
                [
                    f"- **Name:** {application['full_name']}",
                    f"- **Emirates ID:** {application['emirates_id']}",
                    f"- **Family size:** {application['family_size']}",
                    f"- **Net monthly household income:** "
                    f"{application['net_monthly_income_aed']} AED",
                    f"- **Employment status:** "
                    f"{EMPLOYMENT_STATUSES[application['employment_status']]}",
                    f"- **Submitted:** {result['submitted_at']}",
                ]
            )
        )
        _show_decision(result, show_reference_hint=False)
        st.caption(f"Decided {decision['decided_at']} using rule {decision['rule_version']}.")


def _load_review_queue() -> None:
    state = st.session_state
    state.review_items, state.review_failure = None, None
    try:
        state.review_items = get_client().review_queue(state.review_passcode)["items"]
    except ApiError as exc:
        state.review_failure = exc.detail


def render_review(client: ApiClient) -> None:
    st.caption("For caseworkers. Enter the shared caseworker passcode.")
    with st.form("review"):
        st.text_input("Caseworker passcode", key="review_passcode", type="password")
        st.form_submit_button("Show review queue", on_click=_load_review_queue)

    if st.session_state.get("review_failure"):
        st.error(st.session_state.review_failure)
    items = st.session_state.get("review_items")
    if items is None:
        return
    if not items:
        st.info("No applications are waiting for review.")
        return
    st.markdown(f"**{len(items)} application(s) waiting for review**, newest first")
    st.table(
        [
            {
                "Reference": item["reference_number"],
                "Name": item["full_name"],
                "Submitted (UTC)": item["submitted_at"],
                "Flag reason": item["flag_reason"],
            }
            for item in items
        ]
    )


def main() -> None:
    st.set_page_config(page_title="Social Support Assessment", page_icon="🏛️")
    st.title("Social Support Assessment")
    client = get_client()
    apply_tab, lookup_tab, review_tab = st.tabs(["Apply", "Look up", "Review queue"])
    with apply_tab:
        render_apply(client)
    with lookup_tab:
        render_lookup(client)
    with review_tab:
        render_review(client)


main()
