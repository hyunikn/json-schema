package io.github.hyunikn.jsonschema;

import java.math.BigInteger;

import java.util.Objects;

public class UINT64 {
    public UINT64(BigInteger val) {
        if (val == null) {
            throw new Error("val of UINT16's cannot be null");
        }
        if (val.compareTo(MIN_VAL) < 0 || val.compareTo(MAX_VAL) > 0) {
            throw new Error("value " + val + " is out of valid range of UINT64");
        }
        this.val = val;
    }

    public UINT64(long bits) {
        this.val = new BigInteger(1, new byte [] {
            (byte) ((bits & 0xFF00000000000000L) >> 56),
            (byte) ((bits & 0xFF000000000000L) >> 48),
            (byte) ((bits & 0xFF0000000000L) >> 40),
            (byte) ((bits & 0xFF00000000L) >> 32),
            (byte) ((bits & 0xFF000000L) >> 24),
            (byte) ((bits & 0xFF0000L) >> 16),
            (byte) ((bits & 0xFF00L) >> 8),
            (byte)  (bits & 0xFFL)
        });
    }

    public BigInteger val() {
        return val;
    }

    public long bits() {
        return val.longValue();
    }

    public boolean equals(Object o) {
        if (o == null || o.getClass() != UINT64.class) {
            return false;
        }

        UINT64 that = (UINT64) o;
        return Objects.equals(this.val, that.val);
    }

    public int hashCode() {
        return val.hashCode();
    }

    public String toString() {
        return val.toString();
    }

    //-----------------------------------------------------
    // Private
    //-----------------------------------------------------

    private static final BigInteger MIN_VAL = BigInteger.valueOf(0L);
    private static final BigInteger MAX_VAL = new BigInteger("FFFFFFFFFFFFFFFF", 16);

    private BigInteger val;

}
