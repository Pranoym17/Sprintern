export type FilterOptionGroup = { label: string; options: readonly string[] };

export const ROLE_OPTIONS: readonly FilterOptionGroup[] = [
  { label: "All opportunities", options: ["Any role or field"] },
  { label: "Engineering", options: [
    "Software Engineering", "Software Developer", "SWE", "SDE", "Backend Engineering",
    "Frontend Engineering", "Full Stack Engineering", "Mobile Engineering", "iOS Engineering",
    "Android Engineering", "Cloud Engineering", "DevOps", "Site Reliability Engineering",
    "Infrastructure Engineering", "Systems Engineering", "Network Engineering", "Cybersecurity",
    "Quality Assurance", "Test Engineering",
  ] },
  { label: "Data & AI", options: [
    "Data Science", "Data Analytics", "Data Engineering", "Machine Learning",
    "Artificial Intelligence", "Applied Science", "Research Science", "Computer Vision",
    "Natural Language Processing",
  ] },
  { label: "Hardware", options: [
    "Embedded Systems", "Firmware Engineering", "Hardware Engineering", "Electrical Engineering",
    "ASIC Engineering", "FPGA Engineering", "Silicon Engineering", "Verification Engineering",
    "Mechanical Engineering", "Robotics",
  ] },
  { label: "Product & design", options: [
    "Product Management", "Program Management", "Project Management", "UX Design", "UI Design",
    "Product Design", "UX Research",
  ] },
  { label: "Business", options: [
    "Business Analysis", "Consulting", "Quantitative Research", "Quantitative Trading", "Finance",
    "Accounting", "Risk", "Marketing", "Sales", "Operations", "Supply Chain", "Human Resources",
    "Recruiting", "Customer Success",
  ] },
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
