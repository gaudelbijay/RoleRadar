# Resume intelligence

[Documentation index](document.md)

Resume intelligence personalizes the order of jobs that already pass the query,
country, posting-age, education, and domain gates. It does not make an employment
decision or claim that the applicant is qualified.

## Occupational coverage

The deterministic taxonomy currently covers 356 canonical skills, 32 domains,
89 role families, and 21 categories:

- software and web development; data, AI, and analytics
- cloud, DevOps, and cybersecurity
- robotics, electrical, mechanical, civil, construction, and environmental engineering
- science, biotechnology, laboratories, healthcare, and clinical care
- finance, accounting, insurance, business, product, and project management
- marketing, communications, sales, human resources, legal, and compliance
- education, research, writing, design, media, and creative work
- operations, supply chain, quality, customer service, hospitality, and retail
- skilled trades, field service, aerospace, energy, and transportation
- agriculture, food, natural resources, real estate, government, policy, nonprofit,
  and professional/interpersonal skills

Aliases map tools and phrases to canonical skills and categories. The taxonomy is
evidence-based and does not infer skills that are absent from the supplied text.

## Parallel analysis agents

When a CV is uploaded and a search starts, bounded worker agents run in parallel:

1. The resume agent extracts known technical skills, role signals, domains,
   education labels, experience phrases, and public URLs.
2. GitHub agents analyze public profile and repository metadata for up to three
   detected GitHub links. Repositories are not cloned. The agents also discover
   the website on the GitHub profile and homepage URLs attached to repositories.
3. Portfolio agents fetch up to three public HTML/text pages, including websites
   discovered through GitHub, only when the user enables the portfolio opt-in
   control.

The resume agent always runs. Website URLs printed in the CV or stored as embedded
PDF/DOCX hyperlinks are included as supplied evidence. GitHub analysis is enabled
by default and can be disabled. Portfolio analysis is disabled by default and requires opt-in.

## LinkedIn

LinkedIn profile URLs are recognized and shown as user-supplied evidence, but
profile content is not fetched or scraped. Authenticated pages, cookies, and
LinkedIn credentials are never accessed. Users can include relevant public
information directly in their CV when they want it considered.

## URL safety

Only HTTP/HTTPS links are recognized. Public portfolio requests reject URL
credentials, nonstandard ports, localhost, private IP ranges, link-local and
reserved addresses, and redirects to blocked destinations. Requests have short
timeouts and response-size limits. Only public HTML and plain text are read;
links discovered inside fetched pages are not followed.

A public host receives the dashboard server's IP address when its page is
requested. Do not enable portfolio analysis unless that is acceptable.

## Ranking

Resume evidence never bypasses a hard search gate. For eligible jobs, the app
calculates an estimated fit using capped evidence for:

- skills found in both the resume/public evidence and posting
- domain overlap
- role overlap
- education evidence

Personalized order uses 65% resume fit, 25% query relevance, and a 10% optional
city-preference bonus, followed by posting recency for ties. Searches without a
CV retain the original newest-first ordering.

A potential gap means a posting skill was not detected in the supplied evidence;
it does not prove the applicant lacks that skill. Missing job information is
not treated as a candidate deficiency.

## Privacy

Raw CV text and fetched page text remain in the active dashboard process and
are not added to Markdown, PDF, or JSON reports. Reports may contain derived,
non-sensitive match terms and estimated fit scores. Name, email, phone, work
authorization, sponsorship, relocation, photos, and salary expectations are not
ranking inputs.

For a hosted deployment, processing occurs on the hosting server rather than the
user's computer. Do not make a CV-uploading deployment public without an
appropriate privacy notice, access controls, retention policy, and secure
transport.

## GitHub rate limits

Public GitHub data can be read without credentials but is rate-limited. Set a
`GITHUB_TOKEN` environment secret on the server to use a higher authenticated
rate limit. Never commit this token to Git.
