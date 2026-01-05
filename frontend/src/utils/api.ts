/**
 * 金融政策関連データのAPI utilities
 */
import { fetchJson, logApiMeta, type ApiMeta } from './apiUtils'

export interface PolicyRateData {
  date: string
  rate: number
}

export interface PolicyRateResponse {
  data: PolicyRateData[]
  meta: ApiMeta & {
    stale?: boolean
    count: number
  }
}

/**
 * Fed H.15 Policy Rateデータを取得
 */
export const fetchPolicyRate = async (): Promise<PolicyRateData[]> => {
  const result = await fetchJson<PolicyRateResponse>('/api/fed-h15/policy-rate')

  logApiMeta('Policy Rate API', {
    cached: result.meta.cached,
    stale: result.meta.stale,
    response_time_ms: result.meta.response_time_ms,
    count: result.meta.count
  })

  return result.data
}

/**
 * Fed H.15 Policy Rateデータを取得（メタ情報付き）
 */
export const fetchPolicyRateWithMeta = async (): Promise<PolicyRateResponse> => {
  return fetchJson<PolicyRateResponse>('/api/fed-h15/policy-rate')
}
