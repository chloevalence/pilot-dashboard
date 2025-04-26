import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import zipfile
import io
import os
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict
from pandas import ExcelWriter
from matplotlib.backends.backend_pdf import PdfPages
import streamlit_authenticator as stauth


st.set_page_config(page_title="ACSI Emotion Dashboard", layout="wide")

credentials = st.secrets["credentials"].to_dict()
cookie = st.secrets["cookie"]
auto_hash = st.secrets.get("auto_hash", False)

authenticator = stauth.Authenticate(
    credentials,
    cookie["name"],
    cookie["key"],
    cookie["expiry_days"],
    auto_hash=auto_hash,
)

authenticator.login(location='main', key='Login')
authentication_status = st.session_state.get('authentication_status')

if authentication_status is False:
    st.error('Username or password is incorrect')
elif authentication_status:
    st.sidebar.success(f"Welcome, {st.session_state.get('name')}  👋")
    st.title("📞 ACSI Weekly Call Emotion Dashboard")
    st.markdown("Upload your zipped JSON directory — structured like subfolders by date (e.g. 04012025/)")

    # --- Sidebar Section Toggles ---
    st.sidebar.header("Display Options")
    show_summary = st.sidebar.checkbox("📋 Show Summary Table", value=True)
    show_agent = st.sidebar.checkbox("📊 Show Happiness by Agent", value=True)
    show_rolling = st.sidebar.checkbox("📈 Show Rolling Happiness", value=True)
    show_emotion_by_company = st.sidebar.checkbox("🎯 Show Emotion Distribution by Company", value=True)
    show_avg_by_time = st.sidebar.checkbox("📌 Show Happiness by Time of Day", value=True)
    show_duration_vs_happiness = st.sidebar.checkbox("📍 Show Call Duration vs. Avg Happiness", value=True)
    show_confidence = st.sidebar.checkbox("📈 Show Happiness vs. Confidence", value=True)
    show_emotion_by_agent = st.sidebar.checkbox("🧊 Emotion Proportion by Agent", value=True)
    show_duration_by_company = st.sidebar.checkbox("📶 Show Call Duration by Company", value=True)
    show_volume = st.sidebar.checkbox("📞 Show Call Volume by Agent", value=True)


    uploaded_zip = st.file_uploader("Upload ZIP file", type=["zip"])

    company_colors = {
        "Quantum": "#1f77b4",
        "StVincent": "#ff7f0e",
        "ABCMotors": "#2ca02c"
    }

    def mmss_to_seconds(t):
        try:
            minutes, seconds = map(int, t.split(":"))
            return minutes * 60 + seconds
        except:
            return 0

    def process_json(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
        except UnicodeDecodeError:
            try:
                with open(filepath, "r", encoding="latin-1") as f:
                    data = json.load(f)
            except Exception as e:
                print(f"Skipped file {filepath} due to encoding error: {e}")
                return None, None
        except json.JSONDecodeError as e:
            print(f"Skipped file {filepath} due to JSON format error: {e}")
            return None, None

        metadata = data.get("metadata", {})
        low_conf = metadata.get("low_confidences", 0)
        call_id = metadata.get("call_id", filepath.stem)
        agent = metadata.get("agent", "Unknown")
        company = metadata.get("company", "Unknown")
        call_time = metadata.get("time", "Unknown")
        call_date = metadata.get("date", "Unknown")

        graph_data = data.get("emotion_graph", [])
        graph = pd.DataFrame(graph_data)
        if "x" not in graph.columns or "y" not in graph.columns:
            return None, None

        graph["Time (s)"] = graph["x"].apply(mmss_to_seconds)
        graph["Happiness Quotient"] = graph["y"]
        graph["Call ID"] = call_id
        graph["Agent"] = agent
        graph["Company"] = company
        graph["Call Time"] = call_time
        graph["Call Date"] = call_date

        avg_happiness = data.get("average_happiness_value", None)
        speaking_time = sum([mmss_to_seconds(t) for t in data.get("speaking_time_per_speaker", {}).values()])
        emotion_counts = data.get("emotion_counts", {})

        meta = {
            "Call Date": call_date,
            "Call ID": call_id,
            "Agent": agent,
            "Company": company,
            "Call Time": call_time,
            "Avg Happiness": avg_happiness,
            "Call Duration (s)": speaking_time,
            "Low Confidences": low_conf,
            **emotion_counts
        }

        return graph, meta

    def get_all_json_paths(paths):
        json_file_paths = []
        for path in paths:
            if path.suffix == ".json":
                json_file_paths.append(path)
        return json_file_paths



    if uploaded_zip:
        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = Path(tmpdir) / uploaded_zip.name
            with open(zip_path, "wb") as f:
                f.write(uploaded_zip.read())
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(tmpdir)

            json_files = list(Path(tmpdir).rglob("*.json"))
            all_json_paths = get_all_json_paths(json_files)

            graph_frames = []
            meta_rows = []

            for path in all_json_paths:
                gdf, meta = process_json(path)
                if gdf is not None and meta is not None:
                    graph_frames.append(gdf)
                    meta_rows.append(meta)

            if meta_rows:
                meta_df = pd.DataFrame(meta_rows)
                graph_df = pd.concat(graph_frames, ignore_index=True)

                meta_df["Call Duration (min)"] = meta_df["Call Duration (s)"] / 60
                meta_df["Total Emotions"] = meta_df[["happy", "angry", "sad", "neutral"]].sum(axis=1)
                meta_df["Avg Happiness %"] = (meta_df["happy"] / meta_df["Total Emotions"]) * 100
                meta_df["Call Date"] = pd.to_datetime(meta_df["Call Date"], format="%m%d%Y", errors="coerce")
                meta_df.dropna(subset=["Call Date"], inplace=True)

                if meta_df["Call Date"].isnull().all():
                    st.warning("No valid dates found in call metadata.")
                    st.stop()

                # Add dynamic date range filtering
                min_date = meta_df["Call Date"].min()
                max_date = meta_df["Call Date"].max()

                # --- Sidebar Filters ---
                st.sidebar.header("📊 Filter Data")

                # Unique filter options
                companies = meta_df["Company"].dropna().unique().tolist()
                available_agents = meta_df[meta_df["Company"].isin(companies)]["Agent"].dropna().unique().tolist()
                dates = meta_df["Call Date"].dropna().sort_values().dt.date.unique().tolist()

                # --- Date Range Presets ---
                from datetime import date, timedelta

                preset_option = st.sidebar.selectbox(
                    "📆 Date Range Presets",
                    options=["All Time", "This Week", "Last 7 Days", "Last 30 Days", "Custom"],
                    index=0
                )

                if preset_option != "Custom":
                    today = date.today()
                    if preset_option == "All Time":
                        selected_dates = (min(dates), max(dates))
                    elif preset_option == "This Week":
                        selected_dates = (today - timedelta(days=today.weekday()), today)
                    elif preset_option == "Last 7 Days":
                        selected_dates = (today - timedelta(days=7), today)
                    elif preset_option == "Last 30 Days":
                        selected_dates = (today - timedelta(days=30), today)
                else:
                    custom_input = st.sidebar.date_input("Select Date Range", value=(min(dates), max(dates)))
                    # Ensure it's always a tuple of two dates
                    if isinstance(custom_input, tuple) and len(custom_input) == 2:
                        selected_dates = custom_input
                    else:
                        selected_dates = (custom_input, custom_input)
                # Multiselect filters
                selected_companies = st.sidebar.multiselect("Select Companies", companies, default=companies)
                available_agents = meta_df[meta_df["Company"].isin(selected_companies )]["Agent"].dropna().unique().tolist()
                selected_agents = st.sidebar.multiselect("Select Agents", available_agents, default=available_agents)

                # Filter the DataFrame
                filtered_df = meta_df[
                    (meta_df["Company"].isin(selected_companies)) &
                    (meta_df["Agent"].isin(selected_agents)) &
                    (meta_df["Call Date"].dt.date >= selected_dates[0]) &
                    (meta_df["Call Date"].dt.date <= selected_dates[1])
                    ]

                if filtered_df.empty:
                    st.warning("⚠️ No data matches the current filter selection. Please adjust your filters.")
                    st.stop()


            else:
                st.warning("No valid call data was extracted from the JSON files.")
                st.stop()

            summary_data = {
                "Total Calls": [len(filtered_df)],
                "Unique Agents": [filtered_df["Agent"].nunique()],
                "Unique Companies": [filtered_df["Company"].nunique()],
                "Avg Call Duration (min)": [filtered_df["Call Duration (min)"].mean()],
                "Avg Happiness %": [filtered_df["Avg Happiness %"].mean()],
                "Total Low Confidence Segments": [filtered_df["Low Confidences"].sum()],
            }
            summary_df = pd.DataFrame(summary_data)

            if show_summary:
                st.subheader("📋 Summary Metrics")
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Calls", summary_df['Total Calls'].iloc[0])
                col2.metric("Avg Happiness", f"{filtered_df['Avg Happiness %'].mean():.1f}%")
                col3.metric("Avg Duration (min)", f"{filtered_df['Call Duration (min)'].mean():.1f}")
                st.dataframe(summary_df)

            col4, col5 = st.columns(2)
            col6, col7 = st.columns(2)
            col8, col9 = st.columns(2)
            col10, col11 = st.columns(2)
            figures = []
            with col4:
                if show_agent:
                    st.subheader("📊 Average Happiness by Agent")
                    fig1, ax1 = plt.subplots(figsize=(10, 5))
                    filtered_df.groupby("Agent")["Avg Happiness %"].mean().sort_values().plot(kind="barh", ax=ax1, color="teal")
                    ax1.set_xlabel("Avg Happiness (%)")
                    st.pyplot(fig1)
                    figures.append(fig1)

            with col5:
                if show_rolling:
                    st.subheader("📈 Rolling Happiness per Company (7-day)")
                    filtered_df["Total Emotions"] = filtered_df[["happy", "angry", "sad", "neutral"]].sum(axis=1)
                    filtered_df["Happy %"] = filtered_df["happy"] / filtered_df["Total Emotions"] * 100
                    company_roll = filtered_df.groupby(["Call Date", "Company"])["Happy %"].mean().unstack()
                    company_roll = company_roll.rolling(window=7, min_periods=1).mean()
                    fig2, ax2 = plt.subplots(figsize=(10, 4))
                    for company in company_roll.columns:
                        ax2.plot(company_roll.index, company_roll[company], label=company, color=company_colors.get(company))
                    ax2.set_ylabel("Rolling Happiness %")
                    ax2.set_xlabel("Date")
                    ax2.legend()
                    st.pyplot(fig2)
                    figures.append(fig2)

            with col6:
                if show_emotion_by_company:
                    st.subheader("🎯 Emotion Distribution by Company")
                    fig3, ax3 = plt.subplots(figsize=(10, 6))
                    emo_totals = filtered_df.groupby("Company")[["happy", "angry", "sad", "neutral"]].sum()
                    emo_totals.plot(kind="bar", ax=ax3, color=["green", "red", "blue", "orange"])
                    ax3.set_ylabel("Emotion Count")
                    ax3.set_xlabel("Company")
                    ax3.legend(title="Emotion")
                    st.pyplot(fig3)
                    figures.append(fig3)

            with col7:
                if show_avg_by_time:
                    st.subheader("📌 Average Happiness by Time of Day")
                    fig4, ax4 = plt.subplots(figsize=(10, 6))
                    filtered_df.groupby("Call Time")["Avg Happiness %"].mean().plot(kind="bar", ax=ax4, color="orange")
                    ax4.set_xlabel("Call Time")
                    ax4.set_ylabel("Avg Happiness (%)")
                    st.pyplot(fig4)
                    figures.append(fig4)

            with col8:
                if show_duration_vs_happiness:
                    st.subheader("📍 Call Duration vs. Avg Happiness")
                    fig5, ax5 = plt.subplots(figsize=(8, 5))
                    sns.scatterplot(data=filtered_df, x="Call Duration (min)", y="Avg Happiness %", hue="Company", palette=company_colors, ax=ax5)
                    ax5.set_xlabel("Call Duration (min)")
                    ax5.set_ylabel("Avg Happiness (%)")
                    st.pyplot(fig5)
                    figures.append(fig5)

            with col9:
                if show_confidence:
                    st.subheader("📈 Happiness vs. Low Confidence")
                    fig6, ax6 = plt.subplots(figsize=(8, 5))
                    sns.scatterplot(data=filtered_df, x="Low Confidences", y="Avg Happiness %", hue="Company", palette=company_colors, ax=ax6)
                    ax6.set_xlabel("Low Confidence (%)")
                    ax6.set_ylabel("Avg Happiness (%)")
                    st.pyplot(fig6)
                    figures.append(fig6)

            with col10:
                if show_emotion_by_agent:
                    st.subheader("🧊 Emotion Proportion by Agent")
                    emotion_pivot = filtered_df.groupby("Agent")[["happy", "angry", "sad", "neutral"]].sum()
                    emotion_pivot_percent = emotion_pivot.div(emotion_pivot.sum(axis=1), axis=0) * 100
                    fig7, ax7 = plt.subplots(figsize=(10, 6))
                    emotion_pivot_percent.plot(kind='bar', stacked=True, ax=ax7, color=["green", "red", "blue", "orange"])
                    ax7.set_ylabel("Emotion %")
                    ax7.set_xlabel("Agent")
                    st.pyplot(fig7)
                    figures.append(fig7)

            with col11:
                if show_duration_by_company:
                    st.subheader("📶 Avg Call Duration by Company")
                    fig8, ax8 = plt.subplots(figsize=(8, 4))
                    avg_dur = filtered_df.groupby("Company")["Call Duration (min)"].mean()
                    colors = [company_colors.get(c, "gray") for c in avg_dur.index]
                    avg_dur.plot(kind="bar", ax=ax8, color=colors)
                    ax8.set_ylabel("Avg Duration (min)")
                    ax8.set_xlabel("Company")
                    st.pyplot(fig8)
                    figures.append(fig8)

            if show_volume:
                st.subheader("📞 Call Volume per Agent per Day")
                call_volume = filtered_df.groupby(["Call Date", "Agent", "Company"]).size().reset_index(name="Call Count")
                facet = sns.FacetGrid(call_volume, col="Company", col_wrap=2, height=4, sharey=False)
                facet.map_dataframe(sns.lineplot, x="Call Date", y="Call Count", hue="Agent")
                facet.add_legend()
                facet.set_titles("{col_name}")

                # Rotate x-axis labels to avoid overlap
                for ax in facet.axes.flat:
                    for label in ax.get_xticklabels():
                        label.set_rotation(45)
                        label.set_horizontalalignment('right')

                st.pyplot(facet.fig)
                figures.append(facet.fig)

            # --- Create Excel in memory ---
            excel_buffer = io.BytesIO()
            with ExcelWriter(excel_buffer, engine="xlsxwriter") as writer:
                # Data sheets
                filtered_df.to_excel(writer, sheet_name="Call Metadata", index=False)
                summary_df.to_excel(writer, sheet_name="Summary", index=False)

                # Charts sheet
                workbook = writer.book
                worksheet = workbook.add_worksheet("Charts")
                writer.sheets["Charts"] = worksheet

                def insert_plot(fig, cell):
                    imgdata = io.BytesIO()
                    fig.savefig(imgdata, format='png', dpi=150, bbox_inches="tight")
                    imgdata.seek(0)
                    worksheet.insert_image(cell, "", {"image_data": imgdata})

                # Insert all figures in vertical layout
                for i, fig in enumerate(figures):
                    row = i * 25  # space between charts
                    cell = f"A{row + 1}"
                    insert_plot(fig, cell)

            # --- Download Buttons ---
            st.download_button(
                label="📥 Download Raw Data (Excel)",
                data=excel_buffer.getvalue(),
                file_name=f"call_report_{selected_dates[0]}_to_{selected_dates[1]}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # Generate the PDF in memory and offer immediate download
            pdf_buffer = io.BytesIO()
            with PdfPages(pdf_buffer) as pdf:
                for fig in figures:
                    pdf.savefig(fig, bbox_inches='tight')
            pdf_buffer.seek(0)

            st.download_button(
                label="📄 Export All Graphs as PDF",
                data=pdf_buffer,
                file_name="ACSI_Charts.pdf",
                mime="application/pdf"
            )


st.markdown("---")
st.markdown("Built with ❤️ by [Valence](https://www.getvalenceai.com) | ACSI Pilot Dashboard © 2025")
