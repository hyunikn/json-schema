package io.github.hyunikn.jsonschema;

import io.github.hyunikn.jsonden.*;

import io.github.getify.minify.Minify;

import java.math.BigInteger;

import java.io.File;
import java.io.IOException;
import java.io.FileInputStream;

public class JsonSchema {

    // -------------------------------------------------------
    // Public
    // -------------------------------------------------------

    // -------------------------------------------------------------

    public static final int ALL_TAGS = -1;

    public static final int TOP_LEVEL_COMMENT = (1 << 8);
    public static final int DEFAULT_COMMENT = (1 << 7);

    public static Object throwAsExpr(String msg) {
        throw new Error(msg);
    }

    public static JsonObj readAndParseJSON(String filePath, boolean logLoading) {
        FileInputStream in = null;

        if (logLoading) {
            System.out.println("# loading a JSON file " + filePath);
        }

        try {
            File jsonFile = new File(filePath);
            if (!jsonFile.canRead()) {
                throw new Error("cannot read the file");
            }

            in = new FileInputStream(jsonFile);
            int len = in.available();
            if (len == 0) {
                return JsonObj.instance();    // empty json object
            }
            byte [] buf = new byte[len];
            in.read(buf);

            String txt = new String(buf, "UTF-8");
            return JsonObj.parse(txt);

        } catch (Throwable e) {
            throw new Error("cannot parse the JSON file '" + filePath, e);
        } finally {
            if (in != null) {
                try {
                    in.close();
                } catch (IOException e) {
                    System.err.println("failed closing a JSON file " + filePath + ": " + e.getMessage());
                }
            }
        }
    }

    // - parse functions -------------------------------------------

    public static String parseJSONstring(Json jsonVal) {
        if (jsonVal.isNull()) {
            return null;
        } else if (jsonVal.isStr()) {
            return jsonVal.asStr().getString();
        } else {
            throw new Error("value is not of the declared type string, but of " + jsonVal.getClass());
        }
    }

    public static boolean parseJSONbool(Json jsonVal) {
        if (jsonVal.isNull()) {
            throw new Error("value is not of the declared type bool, but is null");
        } else if (jsonVal.isBool()) {
            return jsonVal.asBool().getBoolean();
        } else {
            throw new Error("value is not of the declared type bool, but of " + jsonVal.getClass());
        }
    }

    public static double parseJSONfloat(Json jsonVal) {
        if (jsonVal.isNull()) {
            throw new Error("value is not of the declared type float, but is null");
        } else if (jsonVal.isNum()) {
            return jsonVal.asNum().getDouble();
        } else {
            throw new Error("value is not of the declared type float, but of " + jsonVal.getClass());
        }
    }

    public static byte parseJSONint8(Json jsonVal) {
        BigInteger bi = toBigInteger(jsonVal);
        if (bi.bitLength() < 8) {
            return bi.byteValueExact();
        } else {
            throw new Error("value " + jsonVal + " is out of valid range of the declared type int8");
        }
    }

    public static short parseJSONint16(Json jsonVal) {
        BigInteger bi = toBigInteger(jsonVal);
        if (bi.bitLength() < 16) {
            return bi.shortValueExact();
        } else {
            throw new Error("value " + jsonVal + " is out of valid range of the declared type int16");
        }
    }

    public static int parseJSONint32(Json jsonVal) {
        BigInteger bi = toBigInteger(jsonVal);
        if (bi.bitLength() < 32) {
            return bi.intValueExact();
        } else {
            throw new Error("value " + jsonVal + " is out of valid range of the declared type int32");
        }
    }

    public static long parseJSONint64(Json jsonVal) {
        BigInteger bi = toBigInteger(jsonVal);
        if (bi.bitLength() < 64) {
            return bi.longValueExact();
        } else {
            throw new Error("value " + jsonVal + " is out of valid range of the declared type int64");
        }
    }

    public static short parseJSONuint8(Json jsonVal) {
        BigInteger bi = toBigInteger(jsonVal);
        if (bi.bitLength() <= 8 && bi.compareTo(BigInteger.ZERO) >= 0) {
            return bi.shortValueExact();
        } else {
            throw new Error("value " + jsonVal + " is out of valid range of the declared type uint8");
        }
    }

    public static int parseJSONuint16(Json jsonVal) {
        BigInteger bi = toBigInteger(jsonVal);
        if (bi.bitLength() <= 16 && bi.compareTo(BigInteger.ZERO) >= 0) {
            return bi.intValueExact();
        } else {
            throw new Error("value " + jsonVal + " is out of valid range of the declared type uint16");
        }
    }

    public static long parseJSONuint32(Json jsonVal) {
        BigInteger bi = toBigInteger(jsonVal);
        if (bi.bitLength() <= 32 && bi.compareTo(BigInteger.ZERO) >= 0) {
            return bi.longValueExact();
        } else {
            throw new Error("value " + jsonVal + " is out of valid range of the declared type uint32");
        }
    }

    public static UINT64 parseJSONuint64(Json jsonVal) {
        BigInteger bi = toBigInteger(jsonVal);
        if (bi.bitLength() <= 64 && bi.compareTo(BigInteger.ZERO) >= 0) {
            return new UINT64(bi);
        } else {
            throw new Error("value " + jsonVal + " is out of valid range of the declared type uint64");
        }
    }

    // - end of parse functions -------------------------------------------

    // - pretty-print functions -------------------------------------------

	public static void pprint_string(String val, StringBuffer sbuf) {
        if (val == null) {
            bprint(sbuf, "null");
        } else {
            bprint(sbuf, "\"" + val + "\"");
        }
    }

    public static void pprint_bool(boolean val, StringBuffer sbuf) {
        bprint(sbuf, "" + val);
    }

    public static void pprint_float(double val, StringBuffer sbuf) {
        bprint(sbuf, "" + val);
    }

    public static void pprint_int8(byte val, StringBuffer sbuf) {
        bprint(sbuf, "" + val);
    }

    public static void pprint_int16(short val, StringBuffer sbuf) {
        bprint(sbuf, "" + val);
    }

    public static void pprint_int32(int val, StringBuffer sbuf) {
        bprint(sbuf, "" + val);
    }

    public static void pprint_int64(long val, StringBuffer sbuf) {
        bprint(sbuf, "" + val);
    }

    public static void pprint_uint8(short val, StringBuffer sbuf) {
        bprint(sbuf, "" + val);
    }

    public static void pprint_uint16(int val, StringBuffer sbuf) {
        bprint(sbuf, "" + val);
    }

    public static void pprint_uint32(long val, StringBuffer sbuf) {
        bprint(sbuf, "" + val);
    }

    public static void pprint_uint64(UINT64 val, StringBuffer sbuf) {
        bprint(sbuf, "" + val);
    }

    // - end of pretty-print functions -------------------------------------------

    public static void printIndent(int indent, StringBuffer sbuf) {
        for (int i = 0; i < indent; i++) {
            bprint(sbuf, "  ");
        }
    }

    public static void bprint(StringBuffer sbuf, String str) {
        if (sbuf == null) {
            System.out.print(str);
        } else {
            sbuf.append(str);
        }
    }

    // - end of print util functions -------------------------------------------

    public enum PrintMode {
        PLAIN,
        JSON,
    }

    public enum SetMode {
        UPDATE,
        INSERT,
        REMOVE,
    }

    public enum SetErr {
        OK,
        ERR_GENERAL,

        ERR_BAD_INDEX,
        ERR_DEREF_NULL,
        ERR_DEREF_PRIMITIVE,
        ERR_EMPTY_ARRAY,
        ERR_FAILED_TO_SAVE,
        ERR_INCOMPATIBLE_VAL,
        ERR_INDEX_OUT_OF_RANGE,
        ERR_JSON_PARSE,
        ERR_NO_SUCH_FIELD,
        ERR_NOT_AN_ARRAY,
        ERR_NOT_SETTABLE,
        ERR_UNREACHABLE,
        ERR_WRONG_REVISION,

        ERR_INVALID_REQ_FORMAT,
        ERR_REJECTED_BY_APP,
        ERR_REJECTED_BY_CMD,
    }

    // -------------------------------------------------------
    // Private
    // -------------------------------------------------------

    private static BigInteger toBigInteger(Json obj) {

        BigInteger result = null;

        if (obj.isNull()) {
            throw new Error("value is not of an integer type but is null");
        } else {
            String s = obj.toString();
            try {
                if (s.startsWith("0x")) {
                    result = new BigInteger(s.substring(2), 16);
                } else {
                    result = new BigInteger(s);
                }
            } catch (NumberFormatException e) {
                throw new Error("cannot convert " + s + " into an integer");
            }

            assert result != null;
            return result;
        }
    }
}

