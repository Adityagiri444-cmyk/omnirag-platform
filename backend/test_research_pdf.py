from nodes import generate_research_report
from report_generator import generate_research_report_pdf

result = generate_research_report("SQL query operators and their use cases")
pdf_buffer = generate_research_report_pdf(
    result["topic"], result["report"], result["sources_used"]
)

with open("test_research_output.pdf", "wb") as f:
    f.write(pdf_buffer.read())

print("PDF saved as test_research_output.pdf")