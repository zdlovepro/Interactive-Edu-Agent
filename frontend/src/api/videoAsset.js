import request from '@/utils/request'
import { VIDEO_ASSET_API } from '@/constants/api'

export function listVideoAssets() {
  return request.get(VIDEO_ASSET_API.LIST)
}

export function getVideoAsset(assetId) {
  return request.get(VIDEO_ASSET_API.DETAIL(assetId))
}

export function uploadVideoAsset({ file, name } = {}) {
  const formData = new FormData()
  formData.append('file', file)
  if (name) {
    formData.append('name', name)
  }

  return request.post(VIDEO_ASSET_API.UPLOAD, formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })
}

export function importSampleVideoAsset() {
  return request.post(VIDEO_ASSET_API.IMPORT_SAMPLE)
}

export function transcodeVideoAsset(assetId) {
  return request.post(VIDEO_ASSET_API.TRANSCODE(assetId))
}
