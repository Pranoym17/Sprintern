"""A deliberately small role taxonomy for user-facing internship filters."""

from api.models.enums import RoleCategory

ROLE_CATEGORY_LABELS: dict[RoleCategory, str] = {
    RoleCategory.ALL: "All internship roles",
    RoleCategory.SOFTWARE_ENGINEERING: "Software engineering",
    RoleCategory.AI_ML_DATA: "AI, machine learning & data",
    RoleCategory.CLOUD_INFRASTRUCTURE_SECURITY: "Cloud, infrastructure & security",
    RoleCategory.HARDWARE_EMBEDDED_SILICON: "Hardware, embedded & silicon",
    RoleCategory.PRODUCT_DESIGN_RESEARCH: "Product, design & research",
    RoleCategory.QUANT_FINANCE: "Quant & finance",
    RoleCategory.BUSINESS_OPERATIONS_PEOPLE: "Business, operations & people",
    RoleCategory.OTHER_TECHNICAL: "Other technical roles",
}

# Canonical matcher phrases keep taxonomy policy in one place while role aliases
# remain the implementation detail that recognizes title variations such as SWE.
ROLE_CATEGORY_KEYWORDS: dict[RoleCategory, tuple[str, ...]] = {
    RoleCategory.SOFTWARE_ENGINEERING: (
        "software engineering", "software developer", "backend engineering",
        "frontend engineering", "full stack engineering", "mobile engineering", "qa",
    ),
    RoleCategory.AI_ML_DATA: (
        "data science", "data analytics", "data engineering", "machine learning",
        "artificial intelligence", "ai", "applied science", "research science", "computer vision",
        "natural language processing",
    ),
    RoleCategory.CLOUD_INFRASTRUCTURE_SECURITY: (
        "cloud engineering", "site reliability engineering", "infrastructure engineering",
        "systems engineering", "network engineering", "devops", "security engineering",
    ),
    RoleCategory.HARDWARE_EMBEDDED_SILICON: (
        "embedded systems", "firmware engineering", "hardware engineering",
        "electrical engineering", "asic engineering", "fpga engineering", "silicon engineering",
        "verification engineering", "mechanical engineering", "robotics",
    ),
    RoleCategory.PRODUCT_DESIGN_RESEARCH: (
        "product management", "program management", "project management", "ux design",
        "ui design", "product design", "ux research",
    ),
    RoleCategory.QUANT_FINANCE: (
        "quantitative research", "quantitative trading", "finance", "risk",
    ),
    RoleCategory.BUSINESS_OPERATIONS_PEOPLE: (
        "business analysis", "human resources", "customer success", "supply chain",
        "marketing", "sales", "operations", "consulting", "recruiting",
    ),
    RoleCategory.OTHER_TECHNICAL: (),
    RoleCategory.ALL: (),
}
