package com.interactive.edu.util;

import java.nio.charset.Charset;
import java.nio.charset.StandardCharsets;

public final class TextEncodingRepairer {

    private static final Charset WINDOWS_1252 = Charset.forName("windows-1252");
    private static final String SUSPICIOUS_MOJIBAKE_CHARS =
            "ÃÂÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß"
                    + "àáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿ"
                    + "ŒœŠšŸƒ€™‚„…†‡ˆ‰‹›";
    private static final String CJK_PUNCTUATION = "，。！？：；、“”‘’（）《》【】—…";

    private TextEncodingRepairer() {
    }

    public static String repairIfNeeded(String text) {
        if (text == null || text.isBlank()) {
            return text;
        }

        String latin1Candidate = decodeAsUtf8(text, StandardCharsets.ISO_8859_1);
        String windows1252Candidate = decodeAsUtf8(text, WINDOWS_1252);
        String bestCandidate = pickBetterCandidate(text, latin1Candidate, windows1252Candidate);
        if (bestCandidate == null) {
            return text;
        }

        int originalScore = readabilityScore(text);
        int candidateScore = readabilityScore(bestCandidate);
        boolean suspiciousSource = suspiciousCharCount(text) >= 2 || replacementCharCount(text) > 0;
        boolean candidateClearlyBetter = candidateScore >= originalScore + 4;
        boolean restoresChinese = hanCount(text) == 0 && hanCount(bestCandidate) >= 2;

        if (suspiciousSource && (candidateClearlyBetter || restoresChinese)) {
            return bestCandidate;
        }
        return text;
    }

    private static String pickBetterCandidate(String original, String firstCandidate, String secondCandidate) {
        String best = null;
        int bestScore = Integer.MIN_VALUE;
        for (String candidate : new String[]{firstCandidate, secondCandidate}) {
            if (candidate == null || candidate.equals(original)) {
                continue;
            }
            int score = readabilityScore(candidate);
            if (score > bestScore) {
                best = candidate;
                bestScore = score;
            }
        }
        return best;
    }

    private static String decodeAsUtf8(String text, Charset sourceCharset) {
        return new String(text.getBytes(sourceCharset), StandardCharsets.UTF_8);
    }

    private static int readabilityScore(String text) {
        return hanCount(text) * 4
                + cjkPunctuationCount(text) * 2
                - suspiciousCharCount(text) * 3
                - replacementCharCount(text) * 4;
    }

    private static int hanCount(String text) {
        int count = 0;
        for (int index = 0; index < text.length(); index++) {
            if (Character.UnicodeScript.of(text.charAt(index)) == Character.UnicodeScript.HAN) {
                count++;
            }
        }
        return count;
    }

    private static int suspiciousCharCount(String text) {
        int count = 0;
        for (int index = 0; index < text.length(); index++) {
            if (SUSPICIOUS_MOJIBAKE_CHARS.indexOf(text.charAt(index)) >= 0) {
                count++;
            }
        }
        return count;
    }

    private static int cjkPunctuationCount(String text) {
        int count = 0;
        for (int index = 0; index < text.length(); index++) {
            if (CJK_PUNCTUATION.indexOf(text.charAt(index)) >= 0) {
                count++;
            }
        }
        return count;
    }

    private static int replacementCharCount(String text) {
        int count = 0;
        for (int index = 0; index < text.length(); index++) {
            if (text.charAt(index) == '\uFFFD') {
                count++;
            }
        }
        return count;
    }
}
