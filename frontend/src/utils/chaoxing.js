export function parseChaoxingCourseUrl(url) {
  const value = String(url || '').trim()
  if (!value) {
    return null
  }

  try {
    const parsed = new URL(value)
    const hostname = parsed.hostname.toLowerCase()
    if (!hostname.endsWith('chaoxing.com')) {
      return null
    }

    return {
      courseid: parsed.searchParams.get('courseid') || '',
      clazzid: parsed.searchParams.get('clazzid') || '',
      cpi: parsed.searchParams.get('cpi') || '',
      enc: parsed.searchParams.get('enc') || '',
    }
  } catch {
    return null
  }
}

