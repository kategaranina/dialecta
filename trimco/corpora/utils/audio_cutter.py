import io

import ffmpeg
from django.http import FileResponse

from trimco.settings import DATA_DIR


def cut_audio(audio_path, ms_from, ms_to):
    try:
        out, _ = (
            ffmpeg
            .input(audio_path)
            .filter('atrim', start=ms_from/1000, end=ms_to/1000)
            .output('pipe:', format="mp3")
            .run(capture_stdout=True, capture_stderr=True)
        )
        return io.BytesIO(out), ""
    except ffmpeg.Error as e:
        err = e.stderr.decode('utf8')
        return None, err


def cut_audio_from_request(request):
    buffer, err = cut_audio(
        audio_path=DATA_DIR + request.GET['audio_path'],
        ms_from=int(request.GET['start']),
        ms_to=int(request.GET['end'])
    )
    if err != "":
        return None, err

    buffer.seek(0)
    response = FileResponse(buffer, content_type="audio/mpeg")
    return response, err
