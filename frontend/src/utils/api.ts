/**
 * 金融政策関連データのAPI utilities
 */

export interface PolicyRateData {
  date: string
  rate: number
}

export interface PolicyRateResponse {
  data: PolicyRateData[]
  meta: {
    cached: boolean
    stale?: boolean
    last_updated: string | null
    response_time_ms: number
    count: number
  }
}

/**
 * Fed H.15 Policy Rateデータを取得
 */
export const fetchPolicyRate = async (): Promise<PolicyRateData[]> => {
  try {
    const response = await fetch('/api/fed-h15/policy-rate')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    const result: PolicyRateResponse = await response.json()

    // メタ情報をコンソールに出力（開発時のデバッグ用）
    if (import.meta.env.DEV) {
      console.log('Policy Rate API:', {
        cached: result.meta.cached,
        stale: result.meta.stale,
        response_time_ms: result.meta.response_time_ms,
        count: result.meta.count
      })
    }

    return result.data
  } catch (error) {
    console.error('Error fetching Fed H.15 Policy Rate:', error)
    throw error
  }
}

/**
 * Fed H.15 Policy Rateデータを取得（メタ情報付き）
 */
export const fetchPolicyRateWithMeta = async (): Promise<PolicyRateResponse> => {
  try {
    const response = await fetch('/api/fed-h15/policy-rate')
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`)
    }
    return await response.json()
  } catch (error) {
    console.error('Error fetching Fed H.15 Policy Rate:', error)
    throw error
  }
}
