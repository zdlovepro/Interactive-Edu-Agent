export const SAMPLE_LECTURE_VIDEO_URL =
  import.meta.env.VITE_SAMPLE_LECTURE_VIDEO_URL ||
  'https://interactive-examples.mdn.mozilla.net/media/cc0-videos/flower.mp4'

export const SAMPLE_STANDBY_VIDEO_URL =
  import.meta.env.VITE_SAMPLE_STANDBY_VIDEO_URL ||
  'https://media.w3.org/2010/05/sintel/trailer.mp4'

export const VIDEO_TRACK_MODE = {
  LECTURE: 'lecture',
  STANDBY: 'standby',
}

export const VIDEO_TRACK_LABEL = {
  [VIDEO_TRACK_MODE.LECTURE]: '讲解画面',
  [VIDEO_TRACK_MODE.STANDBY]: '待机画面',
}
