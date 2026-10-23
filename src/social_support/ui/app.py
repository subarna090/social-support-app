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


def _show_decision(result: dict) -> None:
    decision = result["decision"]
    label, colour = OUTCOMES[decision["outcome"]]
    st.subheader("Recommendation")
    st.badge(label, color=colour)
    st.markdown(decision["explanation"])
    if decision["suggested_next_steps"]:
        st.markdown("**Suggested next steps**")
        st.markdown("\n".join(f"- {step}" for step in decision["suggested_next_steps"]))
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
    st.info("Look up a previous application: coming in User Story 2.")


def render_review(client: ApiClient) -> None:
    st.info("Caseworker review queue: coming in User Story 3.")


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
