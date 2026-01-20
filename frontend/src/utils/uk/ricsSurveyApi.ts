/**
 * RICS UK Residential Market Survey API
 * Fetches RICS survey report with forecast chart from the backend
 */

export interface RICSSurveyData {
  report_date: string | null
  pdf_url: string | null
  forecast_image: string | null
  last_updated: string
  error?: string
}

/**
 * Fetch RICS survey data (cached if available)
 */
export async function fetchRICSSurvey(): Promise<RICSSurveyData> {
  const response = await fetch('/api/uk/rics-residential-survey')

  if (!response.ok) {
    throw new Error(`Failed to fetch RICS survey: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * Force refresh RICS survey data (bypass cache)
 */
export async function refreshRICSSurvey(): Promise<RICSSurveyData> {
  const response = await fetch('/api/uk/rics-residential-survey/refresh', {
    method: 'POST'
  })

  if (!response.ok) {
    throw new Error(`Failed to refresh RICS survey: ${response.statusText}`)
  }

  return await response.json()
}

/**
 * Get the full URL for a RICS survey image
 * @param imagePath - Full path or filename of the image (e.g., "cache/uk/.../image.png" or "image.png")
 */
export function getRICSSurveyImageUrl(imagePath: string): string {
  // Extract just the filename from the path
  const fileName = imagePath.split('/').pop() || imagePath
  return `/api/uk/rics-residential-survey/image/${fileName}`
}
