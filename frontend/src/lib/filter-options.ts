export type FilterOptionGroup = { label: string; options: readonly string[] };

export const ROLE_CATEGORY_LABELS: Record<string, string> = {
  all: "All internship roles",
  software_engineering: "Software engineering",
  ai_ml_data: "AI, machine learning & data",
  cloud_infrastructure_security: "Cloud, infrastructure & security",
  hardware_embedded_silicon: "Hardware, embedded & silicon",
  product_design_research: "Product, design & research",
  quant_finance: "Quant & finance",
  business_operations_people: "Business, operations & people",
  other_technical: "Other technical roles",
};

export const ROLE_CATEGORY_OPTIONS: readonly FilterOptionGroup[] = [
  { label: "Everything", options: ["all"] },
  { label: "Engineering", options: ["software_engineering", "cloud_infrastructure_security", "hardware_embedded_silicon"] },
  { label: "Data & product", options: ["ai_ml_data", "product_design_research"] },
  { label: "Business", options: ["quant_finance", "business_operations_people", "other_technical"] },
] as const;

export const LOCATION_OPTIONS: readonly FilterOptionGroup[] = [
  { label: "All locations", options: ["Anywhere", "Remote"] },
  { label: "Canada", options: [
    "Canada", "Toronto, ON", "Vancouver, BC", "Montreal, QC", "Ottawa, ON", "Waterloo, ON",
    "Kitchener, ON", "Calgary, AB", "Edmonton, AB", "Halifax, NS", "Victoria, BC",
    "Winnipeg, MB", "Saskatoon, SK", "Quebec City, QC",
  ] },
  { label: "United States", options: [
    "United States", "New York, NY", "San Francisco, CA", "Seattle, WA", "Boston, MA",
    "Austin, TX", "Chicago, IL", "Los Angeles, CA", "Washington, DC",
  ] },
  { label: "International", options: [
    "United Kingdom", "London, UK", "Europe", "Asia-Pacific",
  ] },
] as const;
